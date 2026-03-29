import json
import boto3
import os
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from geolocation import resolve_geolocation

logger = Logger()

lambda_client = boto3.client('lambda')
cloudwatch_client = boto3.client('cloudwatch')

IMAGE_PROCESSOR_ARN = os.environ['IMAGE_PROCESSOR_ARN']
NAFDAC_VALIDATOR_ARN = os.environ['NAFDAC_VALIDATOR_ARN']


@logger.inject_lambda_context
def handler(event: dict, context: LambdaContext) -> dict:
    """
    Workflow Lambda that orchestrates the verification process
    
    1. Calls Image Processor Lambda to store image and extract NAFDAC number
    2. Calls NAFDAC Validator Lambda to validate the number and store results
    
    Input:
    {
        "image": "base64_encoded_image_data",
        "nafdacNumber": "optional_manual_nafdac_number"
    }
    
    Output:
    {
        "verificationId": "uuid",
        "timestamp": "ISO8601_timestamp",
        "imageKey": "s3_key",
        "nafdacNumber": "nafdac_number",
        "validationResult": {...}
    }
    """
    try:
        # Parse request body
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # Resolve geolocation from request
        geo_data = resolve_geolocation(event)
        logger.info("Resolved geolocation", extra={"geolocation": geo_data})

        # Emit CloudWatch geolocation metrics (non-blocking)
        try:
            # Determine verification type
            has_image = bool(body.get('image'))
            has_manual_nafdac = bool(body.get('nafdacNumber'))
            verification_type = 'ManualNafdacInput' if has_manual_nafdac and not has_image else 'ImageUpload'

            metric_data = [
                {
                    'MetricName': 'VerificationRequestByCountry',
                    'Dimensions': [{'Name': 'Country', 'Value': 'Nigeria' if geo_data['country_name'] == 'Nigeria' else 'Other Countries'}],
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'VerificationRequestByRegion',
                    'Dimensions': [{'Name': 'Region', 'Value': geo_data['region']}],
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': verification_type,
                    'Value': 1,
                    'Unit': 'Count'
                },
            ]

            cloudwatch_client.put_metric_data(
                Namespace='MedicineVerification',
                MetricData=metric_data
            )
        except Exception:
            logger.warning("Failed to emit geolocation metrics", exc_info=True)

        # Step 1: Process image
        logger.info("Invoking Image Processor Lambda")
        image_processor_response = lambda_client.invoke(
            FunctionName=IMAGE_PROCESSOR_ARN,
            InvocationType='RequestResponse',
            Payload=json.dumps(body)
        )
        
        image_result = json.loads(image_processor_response['Payload'].read())
        logger.info(f"Image Processor response: {json.dumps(image_result)}")
        
        if image_result.get('statusCode') != 200:
            logger.warning(f"Image Processor failed, returning error: {json.dumps(image_result)}")
            return image_result
        
        image_data = json.loads(image_result['body'])
        
        # Step 2: Validate NAFDAC number
        logger.info(f"Invoking NAFDAC Validator Lambda for {image_data.get('nafdacNumber')}")
        
        try:
            validator_payload = {**image_data, 'geolocation': geo_data}
            validator_response = lambda_client.invoke(
                FunctionName=NAFDAC_VALIDATOR_ARN,
                InvocationType='RequestResponse',
                Payload=json.dumps(validator_payload)
            )
            
            # Check for function errors
            if 'FunctionError' in validator_response:
                logger.error(f"NAFDAC Validator function error: {validator_response.get('FunctionError')}")
                error_payload = json.loads(validator_response['Payload'].read())
                logger.error(f"Error payload: {json.dumps(error_payload)}")
                
                # Return error response
                error_result = {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'NAFDAC validation failed',
                        'details': error_payload
                    })
                }
                logger.error(f"Returning error response: {json.dumps(error_result)}")
                return error_result
            
            validator_result = json.loads(validator_response['Payload'].read())
            logger.info(f"NAFDAC Validator response: {json.dumps(validator_result)}")
            logger.info(f"Returning final response: {json.dumps(validator_result)}")
            
            return validator_result
            
        except Exception as validator_error:
            logger.exception(f"Error invoking NAFDAC Validator: {str(validator_error)}")
            error_result = {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Failed to invoke NAFDAC validator',
                    'details': str(validator_error)
                })
            }
            logger.error(f"Returning error response: {json.dumps(error_result)}")
            return error_result
        
    except Exception as e:
        logger.exception("Error in verification workflow")
        error_result = {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
        logger.error(f"Returning error response: {json.dumps(error_result)}")
        return error_result
