import json
import boto3
import os

lex_client = boto3.client('lexv2-runtime')

def lambda_handler(event, context):
    # 1. Parse request body
    try:
        body = json.loads(event.get('body', '{}'))
        messages = body.get('messages', [])
        user_text = messages[0]['unstructured']['text']
        
        # This ID is the "Key" to the memory. It must come from the frontend.
        # If the frontend doesn't send one, we use 'guest-session' as a fallback.
        session_id = body.get("sessionId", "guest-session")
        
    except (idxError, KeyError, json.JSONDecodeError):
        return {'statusCode': 400, 'body': 'Invalid Request'}
    print("Session ID:", session_id, "User text:", user_text)
    # 2. Call Lex
    lex_response = lex_client.recognize_text(
        botId=os.environ['BOT_ID'],
        botAliasId=os.environ['BOT_ALIAS_ID'],
        localeId='en_US',
        sessionId=session_id, # Passed from the browser
        text=user_text
    )
    
    # 3. Extract Lex's reply
    # Note: Lex can return multiple messages, we grab the first one
    bot_messages = lex_response.get('messages', [])
    response_text = bot_messages[0]['content'] if bot_messages else "I'm sorry, I'm having trouble thinking right now."
    
    # 4. Return response to API Gateway
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'messages': [{
                'type': 'unstructured',
                'unstructured': {'text': response_text}
            }]
        })
    }
