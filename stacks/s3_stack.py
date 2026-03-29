from aws_cdk import (
    Stack,
    aws_s3 as s3,
    RemovalPolicy,
    Duration
)
from constructs import Construct

class S3Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.image_bucket = s3.Bucket(
            self, "ImageBucket",
            cors=[s3.CorsRule(
                allowed_methods=[
                    s3.HttpMethods.GET,
                    s3.HttpMethods.POST,
                    s3.HttpMethods.PUT
                ],
                allowed_origins=["*"],  # Will be restricted to frontend domain in production
                allowed_headers=["*"],
                max_age=3000
            )],
            removal_policy=RemovalPolicy.RETAIN,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )
