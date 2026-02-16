import json

def lambda_handler(event, context):
    # get event and slots
    intent = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent'].get('slots', {})
    
    if intent == "GreetingIntent":
        message = "Hi there! How can I help you today?"
        
    elif intent == "ThankYouIntent":
        message = "You're welcome!"
        
    elif intent == "DiningSuggestionsIntent":
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


        if None in [location, cuisine, time, people, email]:
            # Let Lex continue collecting slots
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

        # all slots filled
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

