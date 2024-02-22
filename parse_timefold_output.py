import json
from datetime import datetime
from datetime import date
from geopy.geocoders import Nominatim
from geopy.geocoders import GoogleV3
import random, string

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1 import GeoPoint

with open('./timefoldParams.json') as outfile:
    tfold_data = json.load(outfile)

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


routeplan_day = date.today()
routeplan_datetime = datetime.today()

with open('timefold_output2024-02-20-22-33-42.json') as outfile:
    tout = json.load(outfile)


for dep in tout['depots']:
    dep['address'] = reverse_loc(dep['location'])

for cust in tout['customers']:
    cust['address'] = reverse_loc(cust['location'])

vehicles1 = [veh for veh in tout['vehicles'] if veh['customers']]
vehicles2 = [veh for veh in vehicles1 if date_from_str(veh['departureTime']) <= routeplan_day]


routeplans = []
routeplan_day_str = routeplan_day.strftime('%b %d, %Y')
for veh in vehicles2:
    #print(veh)
    depot = list(filter(lambda d: d['id'] == veh['depot'], tout['depots']))
    from_addr = depot[0]['address']
    from_loc = GeoPoint(depot[0]['location'][0], depot[0]['location'][1])
    driving_hours_earned = hr_min_from_seconds(veh['totalDrivingTimeSeconds'])
    stop_num = 0
    for cust_id in veh['customers']:
        route_entry = {}
        stop_num += 1
        cust = list(filter(lambda d: d['id'] == cust_id, tout['customers']))
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


cred = credentials.Certificate('serviceAccountKey.json')
app = firebase_admin.initialize_app(cred)

db = firestore.client()

rplan_collection = db.collection('routeplanui')

for rplan in routeplans:
    doc_id = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=20))
    rplan_collection.document(doc_id).set(rplan)





