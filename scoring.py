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
exam_submission = (get_millis(end_date) - get_millis(start_date)) / (1000 * 60 * 60)  # seconds


def getSecondsFromString(str):
    val = str.split(':')
    return int(val[0]) * 3600 + int(val[1]) * 60 + int(val[2])


def computecheating_score(exam_submission, exam_duration, events_dict):
    cheating_score = 0  # / 100
    keywords = ['Looking', 'Mouth', 'Head']  # events keywords
    looking_score = 0
    mouth_score = 0
    head_score = 0

    # control parameters: X times looking away and talking in a Y exam is considered normal behaviour
    X = 60
    Y = 1800

    # head movements control param
    Z = 10

    # time diff control param, events occuring less than 5 seconds apart in a Y seconds exam are reported
    K = 5

    # weight of consecutive incidents in cheating score
    weight = 7
    # allowed consecutive incidents in a Y seconds exam
    J = 10
    
    looking_threshold = exam_submission * X / Y  # times
    mouth_threshold = exam_submission * X / Y
    head_threshold = exam_submission * Z / Y
#    timeThreshold = exam_submission * K / Y # seconds
    timeThreshold = 5 # seconds
    allowed_incidents = exam_submission * J / Y
    
    print("allowed incidents: {}".format(allowed_incidents))
    
    consecutive_incidents = 0
    previous_events_timestamp = None

    # give a score

    for (timestamp, events) in events_dict.items():
        if not previous_events_timestamp:
            previous_events_timestamp = timestamp
        else:
            time_diff = getSecondsFromString(timestamp) - getSecondsFromString(previous_events_timestamp)
            if time_diff <= timeThreshold:  # seconds
                consecutive_incidents += 1
            else:
                cheating_score += (consecutive_incidents * weight if consecutive_incidents > allowed_incidents else 0)
                consecutive_incidents = 0
            previous_events_timestamp = timestamp
        
        for event in events:
            if keywords[0] in event:
                if looking_score <= looking_threshold:  # seconds
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

    cheating_score += looking_score + mouth_score + head_score + (consecutive_incidents * weight if consecutive_incidents > allowed_incidents else 0)
    print(cheating_score)
    return (100 if cheating_score >= 100 else cheating_score)

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

cheating_score = computecheating_score(exam_submission, exam_duration, events_dict)
print('Cheating score: {}'.format(cheating_score))
eval_ref = db.collection(u'users').document(u'tst123@test.com').collection(u'evaluation').document(examId)
eval_ref.set({'cheatingScore': cheating_score})
