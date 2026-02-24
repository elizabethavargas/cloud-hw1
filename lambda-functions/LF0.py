import json
import boto3
import os

lex_client = boto3.client('lexv2-runtime')

def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")
    
    # Parse request
    body = json.loads(event.get('body', '{}'))
    messages = body.get('messages', [])
    user_text = messages[0]['unstructured']['text']
    
    # Call Lex
    lex_response = lex_client.recognize_text(
        botId=os.environ['BOT_ID'],
        botAliasId=os.environ['BOT_ALIAS_ID'],
        localeId='en_US',
        sessionId=body.get("sessionId", "default-session"),
        text=user_text
    )
    
    # Return response
    response_text = lex_response['messages'][0]['content']
    
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
