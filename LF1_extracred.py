import json
import boto3
import os
from datetime import datetime, date as dt_date, timedelta

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
QUEUE_URL = os.environ['QUEUE_URL']
STATE_TABLE = "user-state"

def lambda_handler(event, context):
    intent = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent'].get('slots', {})
    session_id = event['sessionId'] 
    invocation_source = event["invocationSource"]
    
    table = dynamodb.Table(STATE_TABLE)
    
    # --- INTENT: Greeting ---
    if intent == "GreetingIntent":
        try:
            response = table.get_item(Key={'userId': session_id})
            if 'Item' in response:
                item = response['Item']
                # Auto-trigger SQS for extra credit
                message_body = {
                    "location": item['last_location'],
                    "cuisine": item['last_cuisine'],
                    "email": item['last_email'],
                    "date": str(dt_date.today()),
                    "time": "19:00", "people": "2"
                }
                sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))
                
                return close_intent(intent, f"Welcome back! I remember you liked {item['last_cuisine']} in {item['last_location']}. I've sent fresh suggestions to {item['last_email']}!")
            
            return close_intent(intent, "Hi there! How can I help you today?")
        except Exception as e:
            return close_intent(intent, "Hi there! How can I help you today?")
        
    # --- INTENT: Thank You ---
    elif intent == "ThankYouIntent":
        return close_intent(intent, "You're welcome!")
        
    # --- INTENT: Dining Suggestions ---
    elif intent == "DiningSuggestionsIntent":
        # Helper to get slot values
        def get_slot(name):
            return slots[name]["value"].get("interpretedValue") if slots.get(name) and slots[name].get("value") else None

        location = get_slot('location')
        cuisine = get_slot('cuisine')
        date = get_slot('diningDate')
        time = get_slot('diningTime')
        people = get_slot('numberOfPeople')
        email = get_slot('email')

        # 1. VALIDATION
        if invocation_source == "DialogCodeHook":
            # Validate Location
            if location and location.lower() not in ["manhattan", "manhatten", "manhatan"]:
                return elicit_slot(intent, slots, "location", f"Sorry, I only support Manhattan. Please enter a valid location.")

            # Validate Cuisine
            if cuisine and cuisine.lower() not in ["mexican", "american", "italian", "chinese", "indian"]:
                return elicit_slot(intent, slots, "cuisine", f"I don't have {cuisine}. Please choose Mexican, American, Italian, Chinese, or Indian.")
            
            # Validate People
            if people and (int(people) < 1 or int(people) > 10):
                return elicit_slot(intent, slots, "numberOfPeople", "We can only accommodate 1 to 10 guests. How many people?")
            
            # Validate Date (FIXED: Allow today by subtracting 1 day from today's UTC check)
            if date:
                user_date = datetime.strptime(date, "%Y-%m-%d").date()
                # We use -1 day buffer because AWS servers are often ahead in UTC time
                if user_date < (dt_date.today() - timedelta(days=1)):
                    return elicit_slot(intent, slots, "diningDate", "We cannot book for a past date. What date would you like?")

            # If all validations pass but slots are missing, let Lex ask the next question
            return {"sessionState": {"dialogAction": {"type": "Delegate"}, "intent": {"name": intent, "slots": slots}}}

        # 2. FULFILLMENT
        if invocation_source == "FulfillmentCodeHook":
            # Push to SQS
            message_body = {"location": location, "cuisine": cuisine, "date": date, "time": time, "people": people, "email": email}
            sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))

            # Save state for Extra Credit
            try:
                table.put_item(Item={
                    'userId': session_id,
                    'last_cuisine': cuisine,
                    'last_location': location,
                    'last_email': email
                })
            except: pass

            return close_intent(intent, "Thanks! I've received your request and will email you shortly.")

    return close_intent(intent, "Sorry, I didn't understand that.")

# --- HELPER FUNCTIONS ---
def close_intent(intent_name, message):
    return {
        "sessionState": {"dialogAction": {"type": "Close"}, "intent": {"name": intent_name, "state": "Fulfilled"}},
        "messages": [{"contentType": "PlainText", "content": message}]
    }

def elicit_slot(intent_name, slots, slot_to_elicit, message):
    # Clear the invalid slot so Lex asks for it again
    slots[slot_to_elicit] = None
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_to_elicit},
            "intent": {"name": intent_name, "slots": slots}
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }