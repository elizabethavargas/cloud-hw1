import json
import boto3
import os
from datetime import datetime, date as dt_date, timedelta

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
QUEUE_URL = os.environ['QUEUE_URL']
STATE_TABLE = "user-state" # Ensure this matches your DynamoDB table name

def lambda_handler(event, context):
    intent = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent'].get('slots', {})
    session_id = event['sessionId'] 
    invocation_source = event["invocationSource"]
    
    table = dynamodb.Table(STATE_TABLE)
    
    # --- INTENT: Greeting (The Memory Logic) ---
    if intent == "GreetingIntent":
        try:
            response = table.get_item(Key={'userId': session_id})
            if 'Item' in response:
                item = response['Item']
                cuisine = item['last_cuisine']
                location = item['last_location']
                email = item['last_email']
                
                # 1. AUTOMATIC ACTION: We fulfill the requirement by sending SQS immediately
                message_body = {
                    "location": location,
                    "cuisine": cuisine,
                    "email": email,
                    "date": str(dt_date.today()),
                    "time": "19:00", 
                    "people": "2"
                }
                sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))
                
                # 2. FLEXIBLE RESPONSE: We tell them we did it, but invite a new search
                message = (f"Welcome back! Since you previously searched for {cuisine} in {location}, "
                           f"I've already sent fresh recommendations to {email}. "
                           f"\n\nIf you want something DIFFERENT today, just say 'I want a new restaurant'.")
                return close_intent(intent, message)
            
            # If no memory found, just say Hi
            return close_intent(intent, "Hi there! I'm your dining concierge. How can I help you today?")
        except Exception as e:
            print(f"Error in Greeting: {e}")
            return close_intent(intent, "Hi there! How can I help you today?")
        
    # --- INTENT: Thank You ---
    elif intent == "ThankYouIntent":
        return close_intent(intent, "You're welcome! Enjoy your meal.")
        
    # --- INTENT: Dining Suggestions (The Search & Save Logic) ---
    elif intent == "DiningSuggestionsIntent":
        def get_slot(name):
            return slots[name]["value"].get("interpretedValue") if slots.get(name) and slots[name].get("value") else None

        location = get_slot('location')
        cuisine = get_slot('cuisine')
        date = get_slot('diningDate')
        time = get_slot('diningTime')
        people = get_slot('numberOfPeople')
        email = get_slot('email')

        # 1. VALIDATION (Only runs while asking questions)
        if invocation_source == "DialogCodeHook":
            if location and location.lower() not in ["manhattan", "manhatten", "manhatan"]:
                return elicit_slot(intent, slots, "location", "Sorry, I only support Manhattan right now. Please enter a valid location.")

            if cuisine and cuisine.lower() not in ["mexican", "american", "italian", "chinese", "indian"]:
                return elicit_slot(intent, slots, "cuisine", f"I don't have data for {cuisine}. Try: Mexican, American, Italian, Chinese, or Indian.")
            
            if people and (int(people) < 1 or int(people) > 10):
                return elicit_slot(intent, slots, "numberOfPeople", "I can only book for 1 to 10 guests. How many people in your party?")
            
            if date:
                # Fixed 'Today' bug using a 1-day buffer for UTC timezones
                user_date = datetime.strptime(date, "%Y-%m-%d").date()
                if user_date < (dt_date.today() - timedelta(days=1)):
                    return elicit_slot(intent, slots, "diningDate", "I can't look in the past! Please provide a future date.")

            # If all valid but more info needed, let Lex continue
            return {"sessionState": {"dialogAction": {"type": "Delegate"}, "intent": {"name": intent, "slots": slots}}}

        # 2. FULFILLMENT (Runs when all questions are answered)
        if invocation_source == "FulfillmentCodeHook":
            # Send fresh request to SQS
            message_body = {"location": location, "cuisine": cuisine, "date": date, "time": time, "people": people, "email": email}
            sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))

            # OVERWRITE DynamoDB with the newest search (This updates the 'Memory')
            try:
                table.put_item(Item={
                    'userId': session_id,
                    'last_cuisine': cuisine,
                    'last_location': location,
                    'last_email': email,
                    'updatedAt': str(datetime.now())
                })
            except Exception as e:
                print(f"Error saving state: {e}")

            return close_intent(intent, f"Great! I've received your new request for {cuisine} in {location}. I'll email you shortly.")

    return close_intent(intent, "Sorry, I'm not sure how to help with that.")

# --- HELPERS ---
def close_intent(intent_name, message):
    return {
        "sessionState": {"dialogAction": {"type": "Close"}, "intent": {"name": intent_name, "state": "Fulfilled"}},
        "messages": [{"contentType": "PlainText", "content": message}]
    }

def elicit_slot(intent_name, slots, slot_to_elicit, message):
    slots[slot_to_elicit] = None # Reset the bad slot
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_to_elicit},
            "intent": {"name": intent_name, "slots": slots}
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }