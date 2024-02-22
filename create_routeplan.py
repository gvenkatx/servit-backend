import firebase_admin
from firebase_admin import db
from firebase_admin import credentials, firestore
import json
from google.cloud.firestore_v1 import GeoPoint
from datetime import datetime
import requests
import time
from geopy.geocoders import Nominatim

# Initialize Firebase Admin SDK
cred = credentials.Certificate('./serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Get a reference to the Firestore database
db = firestore.client()

# Gathering specific Document IDs for donors
collection_donor = "customer"
consolidated_data1 = []
collection_refA = db.collection(collection_donor)
document_idsA = [doc.id for doc in collection_refA.stream()]

# Gathering specific Document IDs for teen drivers
collection_driver = "teendriver"
consolidated_data2 = []
collection_refB = db.collection(collection_driver)
document_idsB = [doc.id for doc in collection_refB.stream()]

consolidated_data3 = []
collection_depot = "depot"
collection_refC = db.collection(collection_depot)
document_idsC = [doc.id for doc in collection_refC.stream()]

# Function for gathering data from Documents
def my_function(collection_name, document_id, result_list, persona):
    # Reference to a specific document
    doc_ref = db.collection(collection_name).document(document_id)
    # Get the document snapshot
    doc_snapshot = doc_ref.get()
    # Check if the document exists
    if doc_snapshot.exists:
        # Access the document data
        doc_data = doc_snapshot.to_dict()
        if persona=='customer':
            hardcode_values = {'serviceDuration':1200.000000000, 'vehicle':None, 'previousCustomer':None, 'nextCustomer': None,
                                'arrivalTime':None, 'startServiceTime':None, 'departureTime':None,
                                'drivingTimeSecondsFromPreviousStandstill': None}
            doc_data.update(hardcode_values)

        if persona=='teendriver':
            hardcode_values = {'customers':[], 'totalDemand':0, 'totalDrivingTimeSeconds':0}
            doc_data.update(hardcode_values)

        for key in doc_data:
            if isinstance(doc_data[key], GeoPoint):
                doc_data[key] = [doc_data[key].latitude, doc_data[key].longitude]

            if isinstance(doc_data[key], datetime):
                doc_data[key] = doc_data[key].strftime("%Y-%m-%d" + "T" + "%H:%M:%S")

        #print("Document data:", doc_data)
        result_list.append(doc_data)
        #return(result_list)

# Donor Code
for doc_id in document_idsA:
    my_function(collection_donor, doc_id, consolidated_data1, 'customer')

# Teen Code
for doc_id in document_idsB:
    my_function(collection_driver, doc_id, consolidated_data2, 'teendriver')

# Charitable Orgs
for doc_id in document_idsC:
    my_function(collection_depot, doc_id, consolidated_data3, 'org')


timefoldinput = {"name": "demo","southWestCorner": [36.044659, -80.244217], "northEastCorner": [36.099861,-79.766235],
            "startDateTime": "2024-01-01T07:30:00", "endDateTime": "2024-02-28T00:00:00", 
            "depots": [], "vehicles": [], "customers": [], "totalDrivingTimeSeconds": 0}

timefoldinput['depots'] = consolidated_data3
timefoldinput['customers'] = consolidated_data1
timefoldinput['vehicles'] = consolidated_data2

#timefoldinput['customers'] = [{key: str(value) if key == 'id' else value for key, value in d.items()} for d in timefoldinput['customers']]
timefoldinput['depots'] = [{key: str(value) if key == 'id' else value for key, value in d.items()} for d in timefoldinput['depots']]
timefoldinput['vehicles'] = [{key: str(value) if key == 'depot' else value for key, value in d.items()} for d in timefoldinput['vehicles']]

for item in timefoldinput['customers']:
    item['maxEndTime'] = item.pop('maxStartTime')

for item in timefoldinput['vehicles']:
    item['departureTime'] = item.pop('departuretime')
    item['arrivalTime'] = item.pop('arrivaltime')

format = "%Y-%m-%d-%H-%M-%S"
timefold_input_file = 'timefold_input'+datetime.now().strftime(format)+'.json'
with open(timefold_input_file, 'w') as json_file:
    json.dump(timefoldinput, json_file, indent=2)

with open('./timefoldParams.json') as outfile:
    tfold_data = json.load(outfile)

timefold_url = tfold_data['timefold_url']
headers = {"Content-Type": "application/json", "Accept": "text/plain"}
resp = requests.post(timefold_url, headers = headers, data=json.dumps(timefoldinput))
timefold_jobid = str(resp.text)
print(timefold_jobid)


time.sleep(60)

resp = requests.get(timefold_url + '/' + timefold_jobid, headers = {"Accept": "application/json"})

timefold_output_file = 'timefold_output'+datetime.now().strftime(format)+'.json'
out_file = open(timefold_output_file, 'w')
json.dump(resp.json(), out_file, indent=2)
out_file.close()
