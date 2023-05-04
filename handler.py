import json
import os
from datetime import datetime

import boto3
import requests

MAX_RETRY = os.environ.get('MAX_RETRY', 3)
ALERT_EMAIL = os.environ.get('ALERT_EMAIL')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')
STOCKS_URL = os.environ.get('STOCKS_URL')
TIMEOUT = os.environ.get('TIMEOUT')
HEADERS = {
    "X-RapidAPI-Key": os.environ.get('X_RapidAPI_Key'),
    "X-RapidAPI-Host" : os.environ.get("X_RapidAPI_Host")
}
PARAMS = {
    "exchange": os.environ.get('EXCHANGE'),
    "format": os.environ.get("FORMAT")
}

def lambda_handler(event, context):
    retry_count = event.get('retry_count', 0)

    try:
        # Make API call to external API
        response = requests.get(STOCKS_URL, headers=HEADERS, params=PARAMS)

        if response.status_code == 200:
            data = response.json()
            json_data = json.dumps(data)

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            stock_exchange=PARAMS["exchange"]
            file_name = f'{stock_exchange}_{timestamp}.json'

            # Upload JSON data to S3 bucket
            s3 = boto3.client('s3')
            s3.put_object(Body=json_data, Bucket=OUTPUT_BUCKET, Key=file_name)

            return {
                'statusCode': 200,
                'body': 'Data stored in S3 successfully'
            }
        else:
            raise Exception('Failed to fetch data from the external API')

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        if retry_count < MAX_RETRY:
            retry_count += 1
            # Retry the Lambda function with an incremented retry count
            retry_event = {
                'retry_count': retry_count
            }
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(FunctionName=context.function_name, InvocationType='Event', Payload=json.dumps(retry_event))

            return {
                'statusCode': 500,
                'body': f'Retry attempt {retry_count}/{MAX_RETRY}'
            }
        else:
            # Send alert email
            send_alert_email(str(e))
            return {
                'statusCode': 500,
                'body': 'Exceeded maximum retry attempts. Alert email sent.'
            }


def send_alert_email(error_message):
    subject = 'Lambda Function Failed Multiple Times'
    body = f'The Lambda function has failed more than {MAX_RETRY} times. Error message: {error_message}'

    client = boto3.client('ses')
    response = client.send_email(
        Source=ALERT_EMAIL,
        Destination={
            'ToAddresses': [ALERT_EMAIL]
        },
        Message={
            'Subject': {
                'Data': subject
            },
            'Body': {
                'Text': {
                    'Data': body
                }
            }
        }
    )
