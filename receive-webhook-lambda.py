import json
import random
import time
import uuid
import boto3
import botocore


class dict_to_class(object):
    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])

class evaluator:
    pass


class filters:
    pass


class alertpayload(object):
    def __init__(self, alert):
        alertObj = dict_to_class(alert)
        filterObj = dict_to_class(alertObj.filters)
        evaluatorObj = dict_to_class(alertObj.evaluator)
        
        self.alert_id = alertObj.alert_id
        self.name = alertObj.name
        self.metric = alertObj.metric
        self.evaluator = evaluator()
        self.evaluator.operator = evaluatorObj.operator
        self.evaluator.source = evaluatorObj.source
        self.evaluator.value = evaluatorObj.value
        self.filters = filters()
        
        if hasattr(filterObj, "subaccount_id"):
            self.filters.subaccount_id = filterObj.subaccount_id
        else:
            self.filters.subaccount_id = -1  # set "overall" Health Scores to be -1 for easy identification
        
        self.triggered_value = alertObj.triggered_value
        self.triggered_at = alertObj.triggered_at


def lambda_handler(event, context):

    try:
        alertsList = json.loads(event['body'])

        for alert in alertsList:
            
            alertObj = alertpayload(alert)
            
            # store file in S3
            fileName = get_file_name(alertObj)
            s3_client = boto3.client('s3')
            store_batch(s3_client, json.dumps(alert), fileName)
                
            # write values to database
            dynamodb = boto3.client('dynamodb')
            write_to_dynamodb(alertObj, dynamodb)

        return {
            'statusCode': 200,
            'body': "OK"
        }

    except ValueError as e:

        return {
            'statusCode': 400,
            'body': "Bad Request - " + e
        }


def get_file_name(alertObj):
    alertId = alertObj.alert_id
    subaccountId = alertObj.filters.subaccount_id
    fileName = "HS-{}-{}-{}".format(alertId, subaccountId, str(time.time())).split(".")[0]  # chosen file name convension is HS-subaccount_id-timestamp
    
    return fileName


def write_to_dynamodb(alertObj, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")

    health_score = format(alertObj.triggered_value, ".3f")

    response = dynamodb.put_item(
        TableName='hs_alerts',
        Item={
            'record_id': {'S': str(uuid.uuid4())},
            'alert_id': {'N': str(alertObj.alert_id)},
            'name': {'S': alertObj.name},
            'metric': {'S': alertObj.metric},
            'subaccount_id': {'N': str(alertObj.filters.subaccount_id)},
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
