python
import json
import boto3
import os
import random
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Initialize
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
SES_FROM_EMAIL = os.environ['SES_FROM_EMAIL']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)
ses = boto3.client('ses')

# OpenSearch client
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    'us-east-1',
    'es',
    session_token=credentials.token
)

os_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def lambda_handler(event, context):
    for record in event['Records']:
        message = json.loads(record['body'])
        print(f"Processing: {message}")
        
        # Get recommendations
        restaurants = get_recommendations(message)
        
        # Send email
        send_email(message, restaurants)
    
    return {'statusCode': 200}

def get_recommendations(message):
    cuisine = message['cuisine'].lower()
    
    # Query OpenSearch
    response = os_client.search(
        index='restaurants',
        body={
            'size': 20,
            'query': {'match': {'cuisine': cuisine}}
        }
    )
    
    # Get IDs
    ids = [hit['_source']['restaurant_id'] for hit in response['hits']['hits']]
    
    # Select 3 random
    selected = random.sample(ids, min(3, len(ids)))
    
    # Get from DynamoDB
    restaurants = []
    for rid in selected:
        item = table.get_item(Key={'restaurant_id': rid})
        if 'Item' in item:
            restaurants.append(item['Item'])
    
    return restaurants

def send_email(message, restaurants):
    body = f"Restaurants for {message['cuisine']}:\n\n"
    for i, r in enumerate(restaurants, 1):
        body += f"{i}. {r['name']} - {r['address']} ({r['rating']} stars)\n"
    
    ses.send_email(
        Source=SES_FROM_EMAIL,
        Destination={'ToAddresses': [message['email']]},
        Message={
            'Subject': {'Data': f"{message['cuisine']} Recommendations"},
            'Body': {'Text': {'Data': body}}
        }
    )
