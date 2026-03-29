#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.s3_stack import S3Stack
from stacks.dynamodb_stack import DynamoDBStack
from stacks.lambda_stack import LambdaStack
from stacks.apigateway_stack import ApiGatewayStack
from stacks.frontend_stack import FrontendStack
from stacks.cloudwatch_dashboard_stack import CloudWatchDashboardStack


app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION')
)

# Create S3 stack for image storage
s3_stack = S3Stack(app, "MedicineVerificationS3Stack", env=env)

# Create DynamoDB stack for verification records
dynamodb_stack = DynamoDBStack(app, "MedicineVerificationDynamoDBStack", env=env)

# Create Lambda stack with execution roles and permissions
lambda_stack = LambdaStack(
    app, 
    "MedicineVerificationLambdaStack",
    image_bucket=s3_stack.image_bucket,
    verification_table=dynamodb_stack.verification_table,
    env=env
)

# Create API Gateway stack
api_stack = ApiGatewayStack(
    app, 
    "MedicineVerificationApiStack",
    image_processor=lambda_stack.image_processor,
    nafdac_validator=lambda_stack.nafdac_validator,
    verification_workflow=lambda_stack.verification_workflow,
    env=env
)

# Create Frontend stack
frontend_stack = FrontendStack(
    app, 
    "MedicineVerificationFrontendStack",
    api_url=api_stack.api.url,
    env=env
)

# Add dependencies
lambda_stack.add_dependency(s3_stack)
lambda_stack.add_dependency(dynamodb_stack)
api_stack.add_dependency(lambda_stack)
frontend_stack.add_dependency(api_stack)

# Create CloudWatch Dashboard stack
dashboard_stack = CloudWatchDashboardStack(
    app,
    "MedicineVerificationDashboardStack",
    image_processor=lambda_stack.image_processor,
    nafdac_validator=lambda_stack.nafdac_validator,
    verification_workflow=lambda_stack.verification_workflow,
    api=api_stack.api,
    verification_table=dynamodb_stack.verification_table,
    image_bucket=s3_stack.image_bucket,
    distribution=frontend_stack.distribution,
    image_processor_log_group=lambda_stack.image_processor_log_group,
    nafdac_validator_log_group=lambda_stack.nafdac_validator_log_group,
    verification_workflow_log_group=lambda_stack.verification_workflow_log_group,
    env=env
)

dashboard_stack.add_dependency(s3_stack)
dashboard_stack.add_dependency(dynamodb_stack)
dashboard_stack.add_dependency(lambda_stack)
dashboard_stack.add_dependency(api_stack)
dashboard_stack.add_dependency(frontend_stack)

app.synth()
