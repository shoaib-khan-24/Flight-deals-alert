import time
import requests
from datetime import datetime, timedelta
from twilio.rest import Client
import os

#-------amadeus credentials-------------------------
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
auth_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
amadeus_auth_data = {
    "grant_type": "client_credentials",
    "client_id": AMADEUS_API_KEY,
    "client_secret": AMADEUS_API_SECRET
}
amadeus_auth_headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(url=auth_url, data=amadeus_auth_data, headers=amadeus_auth_headers)
AMADEUS_TOKEN = response.json()['access_token']
amadeus_headers = {
    "Authorization": f"Bearer {AMADEUS_TOKEN}"
}

#---------twilio credentials---------------------------
TWILIO_ACC_SID = os.getenv("TWILIO_ACC_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_MOBILE_NO = os.getenv("TWILIO_MOBILE_NO")
RECEIVER_MOBILE_NO = os.getenv("RECEIVER_MOBILE_NO")
client = Client(TWILIO_ACC_SID , TWILIO_AUTH_TOKEN)

#---------sheety credentials----------------------------
sheety_endpoint = os.getenv("SHEETY_ENDPOINT")
sheety_headers = {
    "Authorization" : os.getenv("SHEETY_AUTH")
}

#------------------------------**** Populating spreadsheet ****-----------------------------------

sheety_response = requests.get(url=sheety_endpoint, headers=sheety_headers)
result = sheety_response.json()['prices']

all_cities = []

for info in result:
    try:
        city_name = info['city']
        amadeus_search_url = f"https://test.api.amadeus.com/v1/reference-data/locations?subType=CITY&keyword={city_name}"
        amadeus_response = requests.get(url=amadeus_search_url, headers=amadeus_headers)

        city_iata_code = amadeus_response.json()['data'][0].get('iataCode')
        all_cities.append(
            {
                "city_iata_code" : city_iata_code,
                "lowest_price" : info["lowestPrice"]
            }
        )

        city_id = info['id']                #to use when put request

        sheety_put_url = f"{sheety_endpoint}/{city_id}"
        new_data = {
            "price":{
                "iataCode" : city_iata_code
            }
        }
        sheety_put_response = requests.put(url=sheety_put_url, json=new_data, headers=sheety_headers)
        # print(sheety_put_response.status_code)
    except IndexError:
        print("Error in getting information for this city.")


#--------------------------------------**** finding both dates ****-------------------------------------
tomorrow_date = datetime.today() + timedelta(days=1)
one_month_later_date = datetime.today() + timedelta(days=31)

#------------------------------------**** finding flight offers ****---------------------------------------

flight_offer_api_endpoint = "https://test.api.amadeus.com/v2/shopping/flight-offers"

origin_city = os.getenv("ORIGIN_CITY")

for city in all_cities:
    date_to_check = tomorrow_date
    best_date = ""
    best_price = float('inf')
    while date_to_check <= one_month_later_date:
        datestr = date_to_check.strftime("%Y-%m-%d")
        flight_parameters = {
            "currencyCode" : "USD",
            "originDestinations": [{
                    "id" : "1",
                    "originLocationCode" : origin_city,
                    "destinationLocationCode" : city["city_iata_code"],
                    "departureDateTimeRange": {"date": datestr}
            }],
            "travelers":[{"id" : "1","travelerType" : "ADULT"}],
            "sources": ["GDS"]
        }
        try:
            flight_offer_response = requests.post(url=flight_offer_api_endpoint, json=flight_parameters,headers=amadeus_headers)
            flight_cost = float(flight_offer_response.json()["data"][0]["price"].get("total"))
            if flight_cost < best_price:
                best_price = flight_cost
                best_date = datestr
        except Exception as e:
            print(f"Error on date {datestr} for city {city["city_iata_code"]}: {e}")
        finally:
            date_to_check += timedelta(days=1)
            time.sleep(1)
    if best_price <= float(city["lowest_price"]):
        message = client.messages.create(
            body=f"Low price alert! Only ${best_price} USD to fly from {origin_city} to {city["city_iata_code"]}, on {best_date}.",
            from_=TWILIO_MOBILE_NO,
            to=RECEIVER_MOBILE_NO
        )
        print(message.body)
