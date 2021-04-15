#!/usr/bin/python
# -*- coding: utf-8 -*-
## python scoring.py ~/Desktop/.

import sys
import json
from google.cloud import storage
import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import dateutil.parser
from datetime import datetime, timezone

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = \
    '/Users/mirunad/Work/examination-platform-791d79b41c1d.json'

fileInput = sys.argv[1]
user = sys.argv[2]

max_int = 2**63 - 1

def get_millis(dt):
    return dt.replace(tzinfo=timezone.utc).timestamp() * 1000


events_dict = {}  # key = timestamp, value = [event]


def parseEvents(specificFile):
    with open(specificFile, 'r') as f:
        contents = [line.rstrip('\n') for line in f]  # list of strings

    for line in contents:
        dictEntry = line.split('&&&')

        # initialize if the key is not present

        if not dictEntry[0] in events_dict:
            events_dict[dictEntry[0]] = []

        # avoid duplicates as multiple events per second can be output from the specific script.

        if not dictEntry[1] in events_dict[dictEntry[0]]:
            events_dict[dictEntry[0]].append(dictEntry[1])


# parse events for all three proctoring capabilities

parseEvents(fileInput + '_eye.txt')
parseEvents(fileInput + '_head.txt')
parseEvents(fileInput + '_mouth.txt')

events_dict = dict(sorted(events_dict.items()))

fileName = fileInput + '_events.txt'
with open(fileName, 'w') as file:
    file.write(json.dumps(events_dict))
print(events_dict)

lastIndexSlash = fileName.rfind('/') + 1
fileNameWithExtension = fileName[lastIndexSlash:]
firstIndexExt = fileNameWithExtension.find('.')
examId = fileNameWithExtension[:firstIndexExt]

# Use the application default credentials
firebase_admin.initialize_app()
db = firestore.client()

print('Adding {} to DB'.format(examId))
events_ref = db.collection(u'users').document(u'tst123@test.com').collection(u'events').document(examId)
events_ref.set(events_dict)

# get exam duration
exam_ref = db.collection(u'exams').document(examId)
examObj = exam_ref.get()
if not examObj:
    raise Error('Exam {} doesn\'t exist in the database.'.format(examId))
exam_dict = examObj.to_dict()
exam_duration = exam_dict['examSpecifications']['examDuration'] * 60  # seconds

# get exam logs
logs_ref = db.collection(u'users').document(u'tst123@test.com').collection(u'logs').document(examId)
logsObj = logs_ref.get()
if not logsObj:
    raise Error('Log {} doesn\'t exist in the database.'.format(examId))
logs_dict = logsObj.to_dict()
actions = logs_dict['actions']
end_date = dateutil.parser.parse(actions[-1]['timestamp'])
start_date = dateutil.parser.parse(actions[0]['timestamp'])
exam_submission = (get_millis(end_date) - get_millis(start_date)) / (1000)  # seconds

# define heuristic types
class Exponential(dict):
  # update typescript if names change
  type
  def __init__(self, score, eye_score, head_score, mouth_score, exam_submission, time_benchmark, eye_benchmark, head_benchmark, mouth_benchmark):
    self.score = score
    self.eye_score = eye_score
    self.head_score = head_score
    self.mouth_score = mouth_score
    self.type = 'exponential'
    self.exam_submission = exam_submission
    self.time_benchmark = time_benchmark
    self.eye_benchmark = eye_benchmark
    self.head_benchmark = head_benchmark
    self.mouth_benchmark = mouth_benchmark

class Consecutive(dict):
  # update typescript if names change
  score = 0
  type
  def __init__(self, incidents, consecutive_weight, time_benchmark):
    self.incidents = incidents
    self.consecutive_weight = consecutive_weight
    self.score = incidents * consecutive_weight
    self.score = self.score if self.score <= 100 else 100
    self.time_benchmark = time_benchmark
    self.type = 'consecutive'

class Correlated(dict):
  # update typescript if names change
  score = 0
  type
  def __init__(self, incidents, correlated_weight, time_benchmark):
    self.incidents = incidents
    self.correlated_weight = correlated_weight
    self.score = incidents * correlated_weight
    self.score = self.score if self.score <= 100 else 100
    self.time_benchmark = time_benchmark
    self.type = 'correlated'

def getSecondsFromString(str):
    val = str.split(':')
    return int(val[0]) * 3600 + int(val[1]) * 60 + int(val[2])
    
def typing(finish_video_timestamp, start_video_timestamp):
    if(not finish_video_timestamp or not start_video_timestamp):
        return False
    sought_finish_timestamp = getSecondsFromString(finish_video_timestamp)
    sought_start_timestamp = getSecondsFromString(start_video_timestamp)
    
    for action in actions:
        if action['actionType'] != "typing" and action['actionType'] != "set_answer":
            continue;
        if action['actionType'] == "typing":
            action_timestamp = (get_millis(dateutil.parser.parse(action['finishedTyping'])) - get_millis(start_date)) / 1000
        if action['actionType'] == "set_answer":
            action_timestamp = (get_millis(dateutil.parser.parse(action['timestamp'])) - get_millis(start_date)) / 1000
        # if student started typing within 5 seconds from looking sideways, we count the incident
        t = action_timestamp - sought_finish_timestamp
        if t <= 5 and t >= 0:
            return True
        # if student typed within the interval start_timestamp and finish_timestamp
        if sought_start_timestamp <= action_timestamp and action_timestamp <= sought_finish_timestamp:
            return True
    return False

def computeCheatingScore(exam_submission, exam_duration, events_dict):
    cheating_score = 0  # / 100
    keywords = ['Looking', 'Mouth', 'Head']  # events keywords
    looking_score = 0
    mouth_score = 0
    head_score = 0

    # control parameters: X times looking away and talking in a Ys exam is considered normal behaviour
    X = 60 * 9 # minutes at most; seconds
    Y = 1800

    # head movements control param
    Z = 10

    # weights
    consecutive_weight = 7 # consecutive_weight of consecutive incidents in cheating score
    correlationWeight = 5 # weight of correlated events
    
    looking_threshold = exam_submission * X / Y  # times
    mouth_threshold = exam_submission * X / Y
    head_threshold = exam_submission * Z / Y
    
    time_threshold = 6 # seconds
    
    consecutive_incidents = 0
    correlated_score = 0
    aux_correlated_score = 0
    
    previous_events_timestamp = None
    previous_looking_timestamp = None
    start_looking_timestamp = None

    # give a score
    for (timestamp, events) in events_dict.items():
        # Consecutive
        if not previous_events_timestamp:
            previous_events_timestamp = timestamp
        else:
            time_diff = getSecondsFromString(timestamp) - getSecondsFromString(previous_events_timestamp)
            if time_diff <= time_threshold:  # seconds
                consecutive_incidents += 1
            else:
                # if the student was not typing, not interested
                if not typing(previous_looking_timestamp, start_looking_timestamp):
                    correlated_score -= aux_correlated_score
                    aux_correlated_score = 0
                start_looking_timestamp = None
            previous_events_timestamp = timestamp
        # Exponential
        for event in events:
            if keywords[0] in event:
                correlated_score += 1;
                aux_correlated_score += 1;
                previous_looking_timestamp = timestamp
                if not start_looking_timestamp:
                    start_looking_timestamp = timestamp
            
                if looking_score <= looking_threshold:
                    looking_score += 1
                else:
                    looking_score += looking_score
            if keywords[1] in event:
                if mouth_score <= mouth_threshold:
                    mouth_score += 1
                else:
                    mouth_score += mouth_score
            if keywords[2] in event:
                if head_score <= head_threshold:
                    head_score += 1
                else:
                    head_score += head_score
    
    if(not typing(previous_looking_timestamp, start_looking_timestamp)):
        aux_correlated_score = 0
    correlated_score += aux_correlated_score
    
    exponential_score = looking_score + mouth_score + head_score
    exponential_score = exponential_score if exponential_score <= 100 else 100
    head_score = head_score if head_score <= max_int else max_int
    looking_score = looking_score if looking_score <= max_int else max_int
    mouth_score = mouth_score if mouth_score <= max_int else max_int
    return (Exponential(exponential_score, looking_score, head_score, mouth_score, exam_submission, Y, X, Z, X), Consecutive(consecutive_incidents, consecutive_weight, time_threshold), Correlated(correlated_score, correlationWeight, time_threshold))

#
#exam_submission = 3600 * 10 / 60
#exam_duration = 3600 * 60 / 60
#events_dict = {
#    '0:00:00': ['Looking right'],
#    '0:00:01': ['Looking right'],
#    '0:00:02': ['Looking right'],
#    '0:00:03': ['Looking left'],
#    '0:01:03': ['Looking left'],
#    '0:01:04': ['Looking left'],
#    '0:01:05': ['Looking left'],
#    '0:01:06': ['Looking left'],
#    '0:01:07': ['Looking left', 'Mouth open'],
#    '0:02:00': ['Looking right'],
#    '0:02:01': ['Looking right'],
#    '0:02:02': ['Looking right'],
#    '0:02:03': ['Looking left'],
#    '0:03:03': ['Looking left'],
#    '0:03:04': ['Looking left'],
#    '0:03:05': ['Looking left'],
#    '0:03:06': ['Looking left'],
#    '0:03:07': ['Looking left', 'Mouth open'],
#    }
#events_dict = {'0:00:00': ['Looking right'], '0:00:01': ['Looking right'], '0:00:02': ['Looking right'], '0:00:03': ['Looking left'], '0:00:05': ['Looking right'], '0:00:06': ['Looking right', 'Looking up', 'Mouth open'], '0:00:07': ['Looking up', 'Looking left'], '0:00:10': ['Looking right', 'Head right'], '0:00:11': ['Looking up', 'Head right', 'Head left', 'Mouth open'], '0:00:12': ['Mouth open'], '0:00:13': ['Looking up', 'Mouth open'], '0:00:14': ['Head left', 'Mouth open']}

# [0]: Exponential, [1]: Consecutive, [2]: Correlated
cheating_scores = computeCheatingScore(exam_submission, exam_duration, events_dict)

firestoreObj = {'exponential': vars(cheating_scores[0]), 'consecutive': vars(cheating_scores[1]), 'correlated': vars(cheating_scores[2])}
print('Score: {}'.format(firestoreObj))
eval_ref = db.collection(u'users').document(user).collection(u'evaluation').document(examId)
eval_ref.set(firestoreObj)
