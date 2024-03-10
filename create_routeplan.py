import random
import string
import firebase_admin
from firebase_admin import db
from firebase_admin import credentials, firestore
import json
from google.cloud.firestore_v1 import GeoPoint
from datetime import date, datetime, timedelta
import requests
import time
from flask import Flask, request
from routeplan_utilities import delete_docs_in_collection, reverse_loc, hr_min_from_seconds, route_distance_and_duration

firebase_cred = credentials.Certificate('./serviceAccountKey.json')
fapp = firebase_admin.initialize_app(firebase_cred)

routeplan_datetime = datetime.utcnow()
routeplan_date = routeplan_datetime.date()

with open('./routeplanParams.json') as pfile:
    tfold_data = json.load(pfile)
routeplan_url = tfold_data['timefold_url']
maps_api_key = tfold_data['maps_api_key']



# Utility function for gathering data from firebase documents
def read_collection(coll_ref, result_list, persona):

    for doc_snapshot in coll_ref.stream():
        doc_data = doc_snapshot.to_dict()
        add_data_flag = False
        #if (persona=='customer' and doc_data['minStartTime'].date() == routeplan_date):
        if (persona=='customer'):
            doc_data['minStartTime'] += timedelta(days=1)
            doc_data['maxStartTime'] += timedelta(days=1)
            if (doc_data['minStartTime'].date() == routeplan_date):
                hardcode_values = {'serviceDuration':1200.000000000, 'vehicle':None, 'previousCustomer':None, 'nextCustomer': None,
                                    'arrivalTime':None, 'startServiceTime':None, 'departureTime':None,
                                    'drivingTimeSecondsFromPreviousStandstill': None}
                doc_data.update(hardcode_values)
                add_data_flag = True
        #elif (persona=='teendriver' and doc_data['departuretime'].date() == routeplan_date):
        elif (persona=='teendriver'):
            doc_data['departuretime'] += timedelta(days=1)
            doc_data['arrivaltime'] += timedelta(days=1)
            if (doc_data['departuretime'].date() == routeplan_date):
                hardcode_values = {'customers':[], 'totalDemand':0, 'totalDrivingTimeSeconds':0}
                doc_data.update(hardcode_values)
                add_data_flag = True 
        elif (persona=='depot'):
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
def create_routeplan_input(firestore_db, routeplaninput):
    
    # Get a reference to the Firestore database
    db = firestore.client()

    # Gathering specific Document IDs for donors
    consolidated_data1 = []
    collection_refA = firestore_db.collection("customer")
    read_collection(collection_refA, consolidated_data1, 'customer')
    routeplaninput['customers'] = consolidated_data1
    for item in routeplaninput['customers']:
        item['maxEndTime'] = item.pop('maxStartTime')

    # Gathering specific Document IDs for teen drivers
    consolidated_data2 = []
    collection_refB = firestore_db.collection("teendriver")
    read_collection(collection_refB, consolidated_data2, 'teendriver')
    routeplaninput['vehicles'] = consolidated_data2
    routeplaninput['vehicles'] = [{key: str(value) if key == 'depot' else value for key, value in d.items()} for d in routeplaninput['vehicles']]
    for item in routeplaninput['vehicles']:
        item['departureTime'] = item.pop('departuretime')
        item['arrivalTime'] = item.pop('arrivaltime')

    consolidated_data3 = []
    collection_refC = firestore_db.collection("depot")
    read_collection(collection_refC, consolidated_data3, 'depot')
    routeplaninput['depots'] = consolidated_data3
    routeplaninput['depots'] = [{key: str(value) if key == 'id' else value for key, value in d.items()} for d in routeplaninput['depots']]


#Main function for parsing routeplan output and writing to firebase
def parse_routeplan_output(firestore_db,routeplanoutput):

    #with open('timefold_output2024-02-20-22-33-42.json') as outfile:
    #    tout = json.load(outfile)

    for dep in routeplanoutput['depots']:
        dep['address'] = reverse_loc(dep['location'], maps_api_key)

    for cust in routeplanoutput['customers']:
        cust['address'] = reverse_loc(cust['location'], maps_api_key)

    vehicles = [veh for veh in routeplanoutput['vehicles'] if veh['customers']]

    routeplans = []
    teenmetrics = []
    routeplan_date_str = routeplan_date.strftime('%b %d, %Y')
    for veh in vehicles:
        #print(veh)
        depot = list(filter(lambda d: d['id'] == veh['depot'], routeplanoutput['depots']))
        from_addr = depot[0]['address']
        from_loc = GeoPoint(depot[0]['location'][0], depot[0]['location'][1])
        gmaps_url = "http://google.com/maps/dir/?api=1&origin="+str(depot[0]['location'][0])+","+str(depot[0]['location'][1])
        +"&destination="+str(depot[0]['location'][0])+","+str(depot[0]['location'][1])+"&waypoints="
        driving_hours_earned = hr_min_from_seconds(veh['totalDrivingTimeSeconds'])
        stop_num = 0
        stops_lat_long = [(depot[0]['location'][0], depot[0]['location'][1])]
        service_duration = 0
        for cust_id in veh['customers']:
            route_entry = {}
            stop_num += 1
            cust = list(filter(lambda d: d['id'] == cust_id, routeplanoutput['customers']))
            stop_addr = cust[0]['address']
            stop_loc = GeoPoint(cust[0]['location'][0], cust[0]['location'][1])
            stops_lat_long.append((cust[0]['location'][0], cust[0]['location'][1]))
            gmaps_url += str(cust[0]['location'][0])+","+str(cust[0]['location'][1])+"|"
            stop_name = cust[0]['name']
            service_duration += hr_min_from_seconds(cust[0]['serviceDuration'])

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
        stops_lat_long.append((depot[0]['location'][0], depot[0]['location'][1]))
        #gmaps_url += "/"+str(depot[0]['location'][0])+","+str(depot[0]['location'][1])
        (total_distance_miles, total_duration_minutes) = route_distance_and_duration(stops_lat_long, maps_api_key)
        #print(f"Total Distance: {total_distance_miles} miles, Total Duration: {total_duration_minutes} minutes")

        route_entry = {'teenid': veh['id'], 'drivinghoursearned': driving_hours_earned, 'routecreateddt':routeplan_datetime,
                        'StopNumber':stop_num, 'donorname': '', 'ToAddress': stop_addr, 'ToLat': stop_loc,
                        'FromAddress': from_addr, 'FromLat': from_loc, 'servicehoursearned': driving_hours_earned}
        routeplans.append(route_entry)

        tm_entry = {'teenid': veh['id'], 'dateserved': routeplan_datetime, 'drivinghoursearned': total_duration_minutes,
                    'servicehoursearned': total_duration_minutes+service_duration, 'cansdonated': veh['totalDemand'],
                    'milesdriven': round(total_distance_miles), 'routeplanurl': gmaps_url} #'displaymetrics': False
        teenmetrics.append(tm_entry)

    rplan_collection = firestore_db.collection('routeplanui')
    rplan_doc_ids = [doc.id for doc in rplan_collection.stream()]
    delete_docs_in_collection(rplan_collection, rplan_doc_ids)
    for rplan in routeplans:
        doc_id = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=20))
        rplan_collection.document(doc_id).set(rplan)

    serveit_milesdriven = 0
    serveit_drivinghours = 0
    serveit_servicehours = 0
    serveit_numdonated = 0
    metric_collection = firestore_db.collection('teenmetrics')
    for tm_entry in teenmetrics:
        docs = metric_collection.where('teenid','==',tm_entry['teenid']).get()
        if docs:
            doc_id = docs[0].id
            curr_data = docs[0].to_dict()
            curr_totaldrivinghours = curr_data['totaldrivinghours']
            curr_totalservicehours = curr_data['totalservicehours']
            curr_totalmilesdriven = curr_data['totalmilesdriven']
        else:
            doc_id = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=20))
            curr_totaldrivinghours = 0
            curr_totalservicehours = 0
            curr_totalmilesdriven = 0
        
        tm_entry['totaldrivinghours'] = curr_totaldrivinghours + tm_entry['drivinghoursearned']
        tm_entry['totalservicehours'] = curr_totalservicehours + tm_entry['servicehoursearned']
        tm_entry['totalmilesdriven'] = curr_totalmilesdriven + tm_entry['milesdriven']
        metric_collection.document(doc_id).set(tm_entry)

        serveit_milesdriven += tm_entry['totalmilesdriven']
        serveit_drivinghours += tm_entry['totaldrivinghours']
        serveit_servicehours += tm_entry['totalservicehours']
        serveit_numdonated += tm_entry['cansdonated']
    #print(teenmetrics)
    
    serveit_metrics = {'totalmilesdriven': serveit_milesdriven, 'totaldrivinghours': serveit_drivinghours,
                       'totalservicehours': serveit_servicehours, 'numdonated': serveit_numdonated,
                       'lastserveddate': routeplan_datetime}
    serveit_collection = firestore_db.collection('serveitmetrics')
    docs = serveit_collection.get()
    if docs:
        doc_id = docs[0].id
    else:
        doc_id = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=20))
    serveit_collection.document(doc_id).set(serveit_metrics)
    #print(serveit_metrics)



#Main app

app = Flask(__name__)

@app.route("/", methods=["GET"])
def create_routeplans():

    db = firestore.client()
    serveit_collection = db.collection('serveitmetrics')
    docs = serveit_collection.get()
    if docs:
        doc_id = docs[0].id
        smetrics = serveit_collection.document(doc_id).get().to_dict()
        if 'lastserveddate' in smetrics: 
            last_served_date = smetrics['lastserveddate'].date()
        else:
            last_served_date = date(1970,1,1)
    else:
        last_served_date = date(1970,1,1)
    if last_served_date >= routeplan_date:
        return("Routeplan will not be created for past date")

    routeplaninput = {"name": "demo","southWestCorner": [36.044659, -80.244217], "northEastCorner": [36.099861,-79.766235],
                        "startDateTime": "2024-01-01T07:30:00", "endDateTime": "2024-02-28T00:00:00", 
                        "depots": [], "vehicles": [], "customers": [], "totalDrivingTimeSeconds": 0}
    create_routeplan_input(db, routeplaninput)

    format = "%Y-%m-%d-%H-%M-%S"
    routeplan_input_file = 'routeplan_input'+datetime.now().strftime(format)+'.json'
    with open(routeplan_input_file, 'w') as json_file:
        json.dump(routeplaninput, json_file, indent=2)

    if not routeplaninput['vehicles']:
        return("No drivers available for route planning!")

    timefold_url = tfold_data['timefold_url']
    headers = {"Content-Type": "application/json", "Accept": "text/plain"}
    resp = requests.post(timefold_url, headers = headers, data=json.dumps(routeplaninput))
    timefold_jobid = str(resp.text)
    with open('./timefold_jobid.txt', 'w') as outfile:
        outfile.write(timefold_jobid)

    time.sleep(60)

    resp = requests.get(timefold_url + '/' + timefold_jobid, headers = {"Accept": "application/json"})
    routeplanoutput = resp.json()

    if 'message' in routeplanoutput:
        return(routeplanoutput['message'])
    else:
        routeplan_output_file = 'routeplan_output'+datetime.now().strftime(format)+'.json'
        with open(routeplan_output_file, 'w') as out_file:
            json.dump(routeplanoutput, out_file, indent=2)
        parse_routeplan_output(db, routeplanoutput)
        return("Success")


if __name__ == '__main__':
    app.run(host="localhost", port=5051, debug=True)

