#Utility functions
from geopy.geocoders import GoogleV3
from datetime import datetime
import requests


def reverse_loc(lat_long, maps_api_key):
    #geolocator = Nominatim(user_agent="mytestapp")
    geolocator = GoogleV3(api_key=maps_api_key)
    location = geolocator.reverse(str(lat_long[0])+","+str(lat_long[1]))
    return location.address

def date_from_str(datestr):
    return datetime.strptime(datestr,'%Y-%m-%dT%H:%M:%S').date()

def hr_min_from_seconds(seconds):
    #minutes, seconds = divmod(seconds, 60)
    #hours, minutes = divmod(minutes, 60)
    #return (str(hours) + ' hr, ' + str(minutes) + ' min')
    return(round(seconds/60))


def get_distance_and_duration(origin_lat_long, destination_lat_long, api_key):
    """Get distance and duration from the Google Maps Distance Matrix API using latitude and longitude."""
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    parameters = {
        'origins': f"{origin_lat_long[0]},{origin_lat_long[1]}",  # Format origin latitude and longitude
        'destinations': f"{destination_lat_long[0]},{destination_lat_long[1]}",  # Format destination latitude and longitude
        'key': api_key,
        'mode': 'driving',
        'language': 'en',
        'units': 'imperial',  # Use imperial units to get distances in miles
    }
    response = requests.get(url, params=parameters)
    data = response.json()
    
    if data['status'] == 'OK':
        distance = data['rows'][0]['elements'][0]['distance']['text']
        duration = data['rows'][0]['elements'][0]['duration']['text']
        return distance, duration
    else:
        print("Error:", data.get('error_message', 'Failed to get a valid response'))
        return None, None

def parse_distance(distance_str):
    """Parse distance string and return distance in miles."""
    # Assuming the distance is always in miles (' mi')
    return float(distance_str.split()[0].replace(',', ''))

def parse_duration(duration_str):
    """Parse duration string and return duration in minutes."""
    total_minutes = 0
    parts = duration_str.split()
    for i in range(0, len(parts), 2):
        if parts[i+1].startswith('hour'):
            total_minutes += int(parts[i]) * 60
        elif parts[i+1].startswith('min'):
            total_minutes += int(parts[i])
    return total_minutes


def route_distance_and_duration(stops_lat_long, api_key):
    total_distance_miles = 0
    total_duration_minutes = 0

    for i in range(len(stops_lat_long) - 1):
        origin_lat_long = stops_lat_long[i]
        destination_lat_long = stops_lat_long[i + 1]
        
        distance, duration = get_distance_and_duration(origin_lat_long, destination_lat_long, api_key)
        if distance and duration:
            distance_miles = parse_distance(distance)
            duration_minutes = parse_duration(duration)
            
            total_distance_miles += distance_miles
            total_duration_minutes += duration_minutes
            
            print(f"From {origin_lat_long} to {destination_lat_long}: Distance = {distance}, Duration = {duration}")

    total_hours, total_mins = divmod(total_duration_minutes, 60)
    return(total_distance_miles, total_duration_minutes)