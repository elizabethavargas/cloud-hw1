import json
import boto3
import os
from datetime import datetime, date as dt_date

sqs = boto3.client('sqs')
QUEUE_URL = os.environ['QUEUE_URL']

def lambda_handler(event, context):
    # get event and slots
    intent = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent'].get('slots', {})
    
    if intent == "GreetingIntent":
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

        # check if location is valid
        if location and location.lower() not in ["manhattan", "manhatten", "manhatan"]:
            return {
                "sessionState": {
                    "dialogAction": {
                        "type": "ElicitSlot",
                        "slotToElicit": "location"
                    },
                    "intent": {
                        "name": intent,
                        "slots": slots,
                        "state": "InProgress"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": f"Sorry, I can't fulfill requests for {location}. Please enter a valid location."
                    }
                ]
            }

        # check if cuisine is valid
        if cuisine and cuisine.lower() not in ["mexican", "american", "italian", "chinese", "indian"]:
            return {
                "sessionState": {
                    "dialogAction": {
                        "type": "ElicitSlot",
                        "slotToElicit": "cuisine"
                    },
                    "intent": {
                        "name": intent,
                        "slots": slots,
                        "state": "InProgress"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": f"Sorry, I can't fulfill requests for {cuisine} cuisine. Please select a cuisine from the following list: American, Chinese, Indian, Italian, Mexican."
                    }
                ]
            }
        
        if people and ((int(people) < 1) or (int(people) > 10)):
            return {
                "sessionState": {
                    "dialogAction": {
                        "type": "ElicitSlot",
                        "slotToElicit": "numberOfPeople"
                    },
                    "intent": {
                        "name": intent,
                        "slots": slots,
                        "state": "InProgress"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": f"We can only accommodate 1 to 10 guests. How many people are in your party?"
                    }
                ]
            }
        
        if date and datetime.strptime(date, "%Y-%m-%d").date() < dt_date.today():
            return {
                "sessionState": {
                    "dialogAction": {
                        "type": "ElicitSlot",
                        "slotToElicit": "diningDate"
                    },
                    "intent": {
                        "name": intent,
                        "slots": slots,
                        "state": "InProgress"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": f"We cannot book for a past date. Please pick a future date."
                    }
                ]
            }

        if None in [location, cuisine, time, people, email, date]:
            # let Lex continue collecting slots
            return {
                "sessionState": {
                    "dialogAction": {
                        "type": "Delegate"
                    },
                    "intent": {
                        "name": intent,
                        "slots": slots,
                        "state": "InProgress"
                    }
                }
            }

        if invocation_source == "DialogCodeHook":
            return {
                "sessionState": {
                    "dialogAction": {"type": "Delegate"},
                    "intent": {
                        "name": intent,
                        "slots": slots,
                        "state": "InProgress"
                    }
                }
            }

        if invocation_source == "FulfillmentCodeHook":
            message_body = {
                "location": location,
                "cuisine": cuisine,
                "date": date,
                "time": time,
                "people": people,
                "email": email
            }

            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(message_body)
            )

            return {
                "sessionState": {
                    "dialogAction": {"type": "Close"},
                    "intent": {
                        "name": intent,
                        "state": "Fulfilled"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": "Thanks! I have received your request and will send restaurant suggestions shortly."
                    }
                ]
            }

        message = "Thanks! I have received your request and will send restaurant suggestions shortly."


    # no intent triggered
    elif intent == "FallbackIntent":
        message = "Sorry, I didn't understand that. I can help you find restaurant suggestions in Manhattan. Try asking, 'I want restaurant ideas.'"
   
   # this should never run
    else:
        message = "Sorry, I didn't understand that."
    
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "name": intent,
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message
            }
        ]
    }
