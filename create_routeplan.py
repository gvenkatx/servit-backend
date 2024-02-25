import random
import string
import firebase_admin
from firebase_admin import db
from firebase_admin import credentials, firestore
import json
from google.cloud.firestore_v1 import GeoPoint
from datetime import date, datetime
import requests
import time
from geopy.geocoders import GoogleV3
from flask import Flask, request

firebase_cred = credentials.Certificate('./serviceAccountKey.json')
fapp = firebase_admin.initialize_app(firebase_cred)

with open('./routeplanParams.json') as pfile:
    tfold_data = json.load(pfile)

routeplan_datetime = datetime.utcnow()
routeplan_day = routeplan_datetime.date()

#Utility functions
def reverse_loc(lat_long):
    #geolocator = Nominatim(user_agent="mytestapp")
    geolocator = GoogleV3(api_key=tfold_data['maps_api_key'])
    location = geolocator.reverse(str(lat_long[0])+","+str(lat_long[1]))
    return location.address

def date_from_str(datestr):
    return datetime.strptime(datestr,'%Y-%m-%dT%H:%M:%S').date()

def hr_min_from_seconds(seconds):
    #minutes, seconds = divmod(seconds, 60)
    #hours, minutes = divmod(minutes, 60)
    #return (str(hours) + ' hr, ' + str(minutes) + ' min')
    return(seconds//60)


# Utility function for gathering data from firebase documents
def read_collection(collection_name, document_id, result_list, persona):

    db = firestore.client()
    # Reference to a specific document
    doc_ref = db.collection(collection_name).document(document_id)
    # Get the document snapshot
    doc_snapshot = doc_ref.get()
    # Check if the document exists
    if doc_snapshot.exists:
        # Access the document data
        doc_data = doc_snapshot.to_dict()
        add_data_flag = False
        if (persona=='customer' and doc_data['minStartTime'].date() == routeplan_day):
            hardcode_values = {'serviceDuration':1200.000000000, 'vehicle':None, 'previousCustomer':None, 'nextCustomer': None,
                                'arrivalTime':None, 'startServiceTime':None, 'departureTime':None,
                                'drivingTimeSecondsFromPreviousStandstill': None}
            doc_data.update(hardcode_values)
            add_data_flag = True
        elif (persona=='teendriver' and doc_data['departuretime'].date() == routeplan_day):
            hardcode_values = {'customers':[], 'totalDemand':0, 'totalDrivingTimeSeconds':0}
            doc_data.update(hardcode_values)
            add_data_flag = True 
        elif (persona=='org'):
            add_data_flag = True
        else: None

        if add_data_flag:
            for key in doc_data:
                if isinstance(doc_data[key], GeoPoint):
                    doc_data[key] = [doc_data[key].latitude, doc_data[key].longitude]

                if isinstance(doc_data[key], datetime):
                    doc_data[key] = doc_data[key].strftime("%Y-%m-%d" + "T" + "%H:%M:%S")

            result_list.append(doc_data)

#Main function to read from firebase and create route plan input
def read_routeplan_input(routeplaninput):
    
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

    # Donor Code
    for doc_id in document_idsA:
        read_collection(collection_donor, doc_id, consolidated_data1, 'customer')

    # Teen Code
    for doc_id in document_idsB:
        read_collection(collection_driver, doc_id, consolidated_data2, 'teendriver')

    # Charitable Orgs
    for doc_id in document_idsC:
        read_collection(collection_depot, doc_id, consolidated_data3, 'org')

    routeplaninput['depots'] = consolidated_data3
    routeplaninput['customers'] = consolidated_data1
    routeplaninput['vehicles'] = consolidated_data2

    #timefoldinput['customers'] = [{key: str(value) if key == 'id' else value for key, value in d.items()} for d in timefoldinput['customers']]
    routeplaninput['depots'] = [{key: str(value) if key == 'id' else value for key, value in d.items()} for d in routeplaninput['depots']]
    routeplaninput['vehicles'] = [{key: str(value) if key == 'depot' else value for key, value in d.items()} for d in routeplaninput['vehicles']]

    for item in routeplaninput['customers']:
        item['maxEndTime'] = item.pop('maxStartTime')

    for item in routeplaninput['vehicles']:
        item['departureTime'] = item.pop('departuretime')
        item['arrivalTime'] = item.pop('arrivaltime')


#Main function for parsing routeplan output and writing to firebase
def parse_routeplan_output(routeplanoutput):

    #with open('timefold_output2024-02-20-22-33-42.json') as outfile:
    #    tout = json.load(outfile)

    for dep in routeplanoutput['depots']:
        dep['address'] = reverse_loc(dep['location'])

    for cust in routeplanoutput['customers']:
        cust['address'] = reverse_loc(cust['location'])

    vehicles = [veh for veh in routeplanoutput['vehicles'] if veh['customers']]
    #vehicles2 = [veh for veh in vehicles1 if date_from_str(veh['departureTime']) <= routeplan_day]

    routeplans = []
    routeplan_day_str = routeplan_day.strftime('%b %d, %Y')
    for veh in vehicles:
        #print(veh)
        depot = list(filter(lambda d: d['id'] == veh['depot'], routeplanoutput['depots']))
        from_addr = depot[0]['address']
        from_loc = GeoPoint(depot[0]['location'][0], depot[0]['location'][1])
        driving_hours_earned = hr_min_from_seconds(veh['totalDrivingTimeSeconds'])
        stop_num = 0
        for cust_id in veh['customers']:
            route_entry = {}
            stop_num += 1
            cust = list(filter(lambda d: d['id'] == cust_id, routeplanoutput['customers']))
            stop_addr = cust[0]['address']
            stop_loc = GeoPoint(cust[0]['location'][0], cust[0]['location'][1])
            stop_name = cust[0]['name']

            route_entry = {'teenid': veh['id'], 'drivinghoursearned': driving_hours_earned, 'routecreateddt':routeplan_datetime,
                        'StopNumber':stop_num, 'donorname': stop_name, 'ToAddress': stop_addr, 'ToLat': stop_loc,
                        'FromAddress': from_addr, 'FromLat': from_loc, 'servicehoursearned': driving_hours_earned}
            routeplans.append(route_entry)

            from_addr = stop_addr
            from_loc = stop_loc
            #print(route_entry)
        stop_num += 1
        stop_addr = depot[0]['address']
        stop_loc = GeoPoint(depot[0]['location'][0], depot[0]['location'][1])
        route_entry = {'teenid': veh['id'], 'drivinghoursearned': driving_hours_earned, 'routecreateddt':routeplan_datetime,
                        'StopNumber':stop_num, 'donorname': '', 'ToAddress': stop_addr, 'ToLat': stop_loc,
                        'FromAddress': from_addr, 'FromLat': from_loc, 'servicehoursearned': driving_hours_earned}
        routeplans.append(route_entry)

    db = firestore.client()
    rplan_collection = db.collection('routeplanui')
    for rplan in routeplans:
        doc_id = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=20))
        rplan_collection.document(doc_id).set(rplan)



app = Flask(__name__)

@app.route("/", methods=["GET"])
def create_routeplans():

    routeplaninput = {"name": "demo","southWestCorner": [36.044659, -80.244217], "northEastCorner": [36.099861,-79.766235],
                        "startDateTime": "2024-01-01T07:30:00", "endDateTime": "2024-02-28T00:00:00", 
                        "depots": [], "vehicles": [], "customers": [], "totalDrivingTimeSeconds": 0}
    read_routeplan_input(routeplaninput)

    format = "%Y-%m-%d-%H-%M-%S"
    routeplan_input_file = 'routeplan_input'+datetime.now().strftime(format)+'.json'
    with open(routeplan_input_file, 'w') as json_file:
        json.dump(routeplaninput, json_file, indent=2)


    timefold_url = tfold_data['timefold_url']
    headers = {"Content-Type": "application/json", "Accept": "text/plain"}
    resp = requests.post(timefold_url, headers = headers, data=json.dumps(routeplaninput))
    timefold_jobid = str(resp.text)
    with open('./timefold_jobid.txt', 'w') as outfile:
        outfile.write(timefold_jobid)

    time.sleep(60)

    resp = requests.get(timefold_url + '/' + timefold_jobid, headers = {"Accept": "application/json"})
    routeplanoutput = resp.json()

    routeplan_output_file = 'routeplan_output'+datetime.now().strftime(format)+'.json'
    with open(routeplan_output_file, 'w') as out_file:
        json.dump(routeplanoutput, out_file, indent=2)

    if 'message' in routeplanoutput:
        return(routeplanoutput['message'])
    else:
        #parse_routeplan_output(routeplanoutput)
        return("Success")


if __name__ == '__main__':
    app.run(host="localhost", port=5051, debug=True)

