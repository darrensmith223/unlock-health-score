import json
import random
import time
import uuid
import boto3
import botocore
from decimal import Decimal


class Dict2Class(object):
    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])


def lambda_handler(event, context):

    try:
        alertsList = json.loads(event['body'])

        for alert in alertsList:
            alertObj = Dict2Class(alert)
            alertId = alertObj.alert_id
            filterObj = Dict2Class(alertObj.filters)
            if hasattr(filterObj, "subaccount_id"):
                subaccountId = filterObj.subaccount_id
            else:
                subaccountId = "overall"
                
            # write values to database
            dynamodb = boto3.client('dynamodb')
            write_to_dynamodb(alertObj, dynamodb)
            
            # store file in S3
            fileName = get_file_name(alertId, subaccountId)
            s3_client = boto3.client('s3')
            store_batch(s3_client, json.dumps(alert), fileName)

        return {
            'statusCode': 200,
            'body': "OK"
        }

    except ValueError as e:

        return {
            'statusCode': 400,
            'body': "Bad Request - " + e
        }


def get_file_name(alertId, subaccountId):
    randomNumber = random.randint(1, 100)
    fileName = "HS-{}-{}-{}".format(alertId, subaccountId, str(time.time())).split(".")[0]  # chosen file name convension is HS-subaccount_id-timestamp
    return fileName


def write_to_dynamodb(alertObj, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
    
    if hasattr(alertObj.filters, "subaccount_id"):
        subaccountId = alertObj.filters.subaccount_id
    else:
        subaccountId = -1  # set "overall" Health Scores to be -1 for easy identification
    
    health_score = Decimal(str(alertObj.triggered_value))  # convert to string then decimal to avoid potential rounding issue

    response = dynamodb.put_item(
        TableName='hs_alerts',
        Item={
            'record_id': {'S': str(uuid.uuid4())},
            'alert_id': {'N': str(alertObj.alert_id)},
            'name': {'S': alertObj.name},
            'metric': {'S': alertObj.metric},
            'subaccount_id': {'N': str(subaccountId)},
            'triggered_value': {'N': str(health_score)},  
            'triggered_at': {'S': alertObj.triggered_at}
        }
    )
    return response
    

def store_batch(s3_client, body, batch_id):
    bucket_name = 'cst-darren'
    try:
        try:
            _ = s3_client.get_object(Bucket=bucket_name, Key=batch_id)
            return

        except botocore.exceptions.ClientError as err:
            e = err.response['Error']['Code']
            if e in ['NoSuchKey', 'AccessDenied']:
                # Forward path. Object does not exist already, so try to create it
                s3_client.put_object(Body=body, Bucket=bucket_name, Key=batch_id)
            else:
                print(err)

    except Exception as err:
        print(err)
        return
