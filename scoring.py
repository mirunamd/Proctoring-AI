import sys
import json
from google.cloud import storage
import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/Users/mirunad/Work/examination-platform-791d79b41c1d.json"

fileInput = sys.argv[1]

eventsDict = {} # key = timestamp, value = [event]

def parseEvents(specificFile):
    with open(specificFile, 'r') as f:
        contents = [line.rstrip('\n') for line in f] # list of strings
       
    for line in contents:
        dictEntry = line.split("&&&")
        # initialize if the key is not present
        if(not dictEntry[0] in eventsDict):
            eventsDict[dictEntry[0]] = []
        # avoid duplicates as multiple events per second can be output from the specific script.
        if(not dictEntry[1] in eventsDict[dictEntry[0]]):
            eventsDict[dictEntry[0]].append(dictEntry[1])

# parse events for all three proctoring capabilities
parseEvents(fileInput + '_eye.txt')
parseEvents(fileInput + '_head.txt')
parseEvents(fileInput + '_mouth.txt')

fileName = fileInput + '_events.txt'
with open(fileName, 'w') as file:
    file.write(json.dumps(eventsDict))
print(eventsDict)

#def upload_blob(bucket_name, source_file_name, destination_blob_name):
#    """Uploads a file to the bucket."""
#    # bucket_name = "your-bucket-name"
#    # source_file_name = "local/path/to/file"
#    # destination_blob_name = "storage-object-name"
#
#    storage_client = storage.Client()
#    bucket = storage_client.bucket(bucket_name)
#    blob = bucket.blob(destination_blob_name)
#
#    blob.upload_from_filename(source_file_name)
#
#    print(
#        "File {} uploaded to {}.".format(
#            source_file_name, destination_blob_name
#        )
#    )
#

lastIndexSlash = fileName.rfind('/') + 1
fileNameWithExtension = fileName[lastIndexSlash:]
firstIndexExt = fileNameWithExtension.find('.')
examId = fileNameWithExtension[:firstIndexExt]

#upload_blob("examination-platform.appspot.com", fileName, "results/tst123@test.com/" + examId)


# Use the application default credentials
firebase_admin.initialize_app()
db = firestore.client()

print("Adding {} to DB".format(examId))

doc_ref = db.collection(u'users').document(u'tst123@test.com').collection(u'events').document(examId)
doc_ref.set(eventsDict)
