import json
import boto3
import os
from datetime import datetime, date as dt_date
from zoneinfo import ZoneInfo
from opensearchpy import OpenSearch, RequestsHttpConnection
import random

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
QUEUE_URL = os.environ['QUEUE_URL']

STATE_TABLE = "user-state"
RESTAURANT_TABLE = "yelp-restaurants"

OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
OPENSEARCH_USER = os.environ['OPENSEARCH_USER']
OPENSEARCH_PASS = os.environ['OPENSEARCH_PASS']

dynamodb = boto3.resource('dynamodb')
restaurant_table = dynamodb.Table(RESTAURANT_TABLE)


os_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def get_recommendations(cuisine):
    cuisine = cuisine.lower()
    
    # Query OpenSearch
    response = os_client.search(
        index='restaurants',
        body={
            'size': 20,
            'query': {'match': {'Cuisine': cuisine}}
        }
    )
    
    # Get IDs
    ids = [hit['_source']['RestaurantID'] for hit in response['hits']['hits']]
    
    # Select 3 random
    selected = random.sample(ids, min(3, len(ids)))
    
    # Get from DynamoDB
    restaurants = []
    for rid in selected:
        item = restaurant_table.get_item(Key={'businessId': rid})
        if 'Item' in item:
            restaurants.append(item['Item'])
    
    return restaurants


def lambda_handler(event, context):
    intent = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent'].get('slots', {})
    session_id = event['sessionId'] # Unique ID for the current user
    
    state_table = dynamodb.Table(STATE_TABLE)
    if intent == "WelcomeIntent":
        message = "Hi there! How can I help you today?"
        # EXTRA CREDIT: Check if user has a previous search
        try:
            response = state_table.get_item(Key={'userId': session_id})
            if 'Item' in response:
                item = response['Item']
                last_cuisine = item['last_cuisine']
                last_location = item['last_location']
                last_email = item['last_email']
                greeting_used = item.get('greeting_used', False)

                if not greeting_used:
                    restaurants = get_recommendations(last_cuisine)

                    message = (f"Welcome back! I remember you liked {last_cuisine} in {last_location}. Here are some restaurant suggestions:\n")
                    for i, r in enumerate(restaurants, 1):
                        message += (
                            f"{i}. {r.get('name', 'Unknown')} - "
                            f"{r.get('address', 'No address')} "
                            f"({r.get('rating', 'No rating')} stars)\n"
                        )
                    # After sending welcome-back message
                    state_table.update_item(
                        Key={'userId': session_id},
                        UpdateExpression="SET greeting_used = :val",
                        ExpressionAttributeValues={':val': True}
                    )
                
        except Exception as e:
            print(f"Error checking state: {e}")
            message = "Hi there! How can I help you today?"

    elif intent == "GreetingIntent":
        message = "Hi there! How can I help you today?"
       
    elif intent == "ThankYouIntent":
        message = "You're welcome!"
        
    elif intent == "DiningSuggestionsIntent":
        invocation_source = event["invocationSource"]
    
        location = slots['location']["value"].get("interpretedValue") if slots.get('location') and slots['location'].get("value") else None
        cuisine = slots['cuisine']["value"].get("interpretedValue") if slots.get('cuisine') and slots['cuisine'].get("value") else None
        date = slots['diningDate']["value"].get("interpretedValue") if slots.get('diningDate') and slots['diningDate'].get("value") else None
        time = slots['diningTime']["value"].get("interpretedValue") if slots.get('diningTime') and slots['diningTime'].get("value") else None
        people = slots['numberOfPeople']["value"].get("interpretedValue") if slots.get('numberOfPeople') and slots['numberOfPeople'].get("value") else None
        email = slots['email']["value"].get("interpretedValue") if slots.get('email') and slots['email'].get("value") else None

        if location and location.lower() not in ["manhattan", "manhatten", "manhatan"]:
            return elicit_slot(intent, slots, "location", f"Sorry, I can't fulfill requests for {location}. Please enter a valid location.")

        if cuisine and cuisine.lower() not in ["mexican", "american", "italian", "chinese", "indian"]:
            return elicit_slot(intent, slots, "cuisine", f"Sorry, I don't have {cuisine}. Try American, Chinese, Indian, Italian, or Mexican.")
        
        if people and ((int(people) < 1) or (int(people) > 10)):
            return elicit_slot(intent, slots, "numberOfPeople", "We can only accommodate 1 to 10 guests. How many people?")

        if date and datetime.strptime(date, "%Y-%m-%d").date() < datetime.now(ZoneInfo("America/New_York")).date(): #datetime.date.today():
            return elicit_slot(intent, slots, "diningDate", "We cannot book for a past date. Please pick a future date.")

        if None in [location, cuisine, time, people, email, date]:
            return {"sessionState": {"dialogAction": {"type": "Delegate"}, "intent": {"name": intent, "slots": slots, "state": "InProgress"}}}

        if invocation_source == "FulfillmentCodeHook":
            # 1. Send to SQS
            message_body = {"location": location, "cuisine": cuisine, "date": date, "time": time, "people": people, "email": email}
            sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))

            # 2. EXTRA CREDIT: Save state to DynamoDB
            try:
                state_table.put_item(Item={
                    'userId': session_id,
                    'last_cuisine': cuisine,
                    'last_location': location,
                    'last_email': email,
                    'timestamp': str(datetime.now()),
                    'greeting_used': False
                })
            except Exception as e:
                print(f"Error saving state: {e}")

            return {
                "sessionState": {"dialogAction": {"type": "Close"}, "intent": {"name": intent, "state": "Fulfilled"}},
                "messages": [{"contentType": "PlainText", "content": "Thanks! I've received your request and saved your preferences. I'll email you shortly!"}]
            }

        return {"sessionState": {"dialogAction": {"type": "Delegate"}, "intent": {"name": intent, "slots": slots, "state": "InProgress"}}}

    elif intent == "FallbackIntent":
        message = "Sorry, I didn't understand that."
    else:
        message = "Sorry, I didn't understand that."
    
    return {
        "sessionState": {"dialogAction": {"type": "Close"}, "intent": {"name": intent, "state": "Fulfilled"}},
        "messages": [{"contentType": "PlainText", "content": message}]
    }



# Helper function to reduce code repetition
def elicit_slot(intent_name, slots, slot_to_elicit, message):
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_to_elicit},
            "intent": {"name": intent_name, "slots": slots, "state": "InProgress"}
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }

