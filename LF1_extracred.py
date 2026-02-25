import json
import boto3
import os
from datetime import datetime, date as dt_date

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
QUEUE_URL = os.environ['QUEUE_URL']
# Ensure you create this table in DynamoDB first!
STATE_TABLE = "user-state"

def lambda_handler(event, context):
    intent = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent'].get('slots', {})
    session_id = event['sessionId'] # Unique ID for the current user
    
    table = dynamodb.Table(STATE_TABLE)
    
    if intent == "GreetingIntent":
        # EXTRA CREDIT: Check if user has a previous search
        try:
            response = table.get_item(Key={'userId': session_id})
            if 'Item' in response:
                item = response['Item']
                last_cuisine = item['last_cuisine']
                last_location = item['last_location']
                last_email = item['last_email']
                
                # AUTOMATICALLY push to SQS
                message_body = {
                    "location": last_location,
                    "cuisine": last_cuisine,
                    "email": last_email,
                    "date": str(dt_date.today()),
                    "time": "19:00", # Default time for auto-suggest
                    "people": "2"     # Default people
                }
                
                sqs.send_message(
                    QueueUrl=QUEUE_URL,
                    MessageBody=json.dumps(message_body)
                )
                
                message = f"Welcome back! I remember you liked {last_cuisine} in {last_location}. I've already sent fresh suggestions to {last_email}!"
            else:
                message = "Hi there! How can I help you today?"
        except Exception as e:
            print(f"Error checking state: {e}")
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

        # --- Your Validation Logic ---
        if location and location.lower() not in ["manhattan", "manhatten", "manhatan"]:
            return elicit_slot(intent, slots, "location", f"Sorry, I can't fulfill requests for {location}. Please enter a valid location.")

        if cuisine and cuisine.lower() not in ["mexican", "american", "italian", "chinese", "indian"]:
            return elicit_slot(intent, slots, "cuisine", f"Sorry, I don't have {cuisine}. Try American, Chinese, Indian, Italian, or Mexican.")
        
        if people and ((int(people) < 1) or (int(people) > 10)):
            return elicit_slot(intent, slots, "numberOfPeople", "We can only accommodate 1 to 10 guests. How many people?")
        
        if date and datetime.strptime(date, "%Y-%m-%d").date() < dt_date.today():
            return elicit_slot(intent, slots, "diningDate", "We cannot book for a past date. Please pick a future date.")

        if None in [location, cuisine, time, people, email, date]:
            return {"sessionState": {"dialogAction": {"type": "Delegate"}, "intent": {"name": intent, "slots": slots, "state": "InProgress"}}}

        if invocation_source == "FulfillmentCodeHook":
            # 1. Send to SQS
            message_body = {"location": location, "cuisine": cuisine, "date": date, "time": time, "people": people, "email": email}
            sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))

            # 2. EXTRA CREDIT: Save state to DynamoDB
            try:
                table.put_item(Item={
                    'userId': session_id,
                    'last_cuisine': cuisine,
                    'last_location': location,
                    'last_email': email,
                    'timestamp': str(datetime.now())
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