from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_logs as logs,
)
from constructs import Construct

class LambdaStack(Stack):

    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        image_bucket: s3.Bucket,
        verification_table: dynamodb.Table,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Lambda layer for shared dependencies (boto3, aws-lambda-powertools)
        layer = _lambda.LayerVersion(
            self, 'SharedLayer',
            code=_lambda.Code.from_asset('./layer/layer.zip'),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared dependencies for Lambda functions"
        )

        # ========================================
        # Image Processing & OCR Lambda
        # ========================================
        image_processor_log_group = logs.LogGroup(
            self, 'ImageProcessorLogGroup',
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )

        self.image_processor = _lambda.Function(
            self, "ImageProcessorFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="image_processor.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=512,
            log_group=image_processor_log_group,
            architecture=_lambda.Architecture.ARM_64,
            description="Processes base64 images, stores in S3, and extracts NAFDAC number via OCR",
            environment={
                "POWERTOOLS_SERVICE_NAME": "ImageProcessor",
                "POWERTOOLS_METRICS_NAMESPACE": "MedicineVerification",
                "LOG_LEVEL": "INFO",
                "IMAGE_BUCKET_NAME": image_bucket.bucket_name
            },
            layers=[layer]
        )

        # Grant S3 permissions
        image_bucket.grant_read_write(self.image_processor)
        
        # Grant Textract permissions for OCR
        self.image_processor.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    'textract:DetectDocumentText',
                    'textract:AnalyzeDocument'
                ],
                resources=['*']
            )
        )
        
        # Grant Bedrock permissions for product name extraction
        self.image_processor.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    'bedrock:InvokeModel'
                ],
                resources=[
                    f'arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0'
                ]
            )
        )

        # Grant CloudWatch PutMetricData for NafdacNotFound custom metric
        self.image_processor.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )
        

        # ========================================
        # NAFDAC Validator Lambda (Container)
        # ========================================
        validator_log_group = logs.LogGroup(
            self, 'ValidatorLogGroup',
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )

        self.nafdac_validator = _lambda.DockerImageFunction(
            self, "ValidatorFunction",
            code=_lambda.DockerImageCode.from_image_asset(
                directory="lambda",
                file="Dockerfile"
            ),
            timeout=Duration.seconds(120),
            memory_size=2048,
            log_group=validator_log_group,
            architecture=_lambda.Architecture.X86_64,
            description="Validates NAFDAC numbers by scraping Greenbook using Selenium with Chrome",
            environment={
                "POWERTOOLS_SERVICE_NAME": "NAFDACValidator",
                "POWERTOOLS_METRICS_NAMESPACE": "MedicineVerification",
                "LOG_LEVEL": "INFO",
                "CHROME_BIN": "/opt/chrome-linux64/chrome",
                "CHROMEDRIVER_BIN": "/opt/chromedriver-linux64/chromedriver",
                "VERIFICATION_TABLE_NAME": verification_table.table_name,
                "IMAGE_BUCKET_NAME": image_bucket.bucket_name
            }
        )
        
        # Grant permissions
        verification_table.grant_read_write_data(self.nafdac_validator)
        image_bucket.grant_read(self.nafdac_validator)

        # Provisioned concurrency to avoid cold start timeouts (Selenium + Chrome is heavy)
        validator_alias = self.nafdac_validator.add_alias(
            "live",
            provisioned_concurrent_executions=1,
        )
        self.nafdac_validator_alias = validator_alias
        
        # Note: Lambda Insights layer is not compatible with Docker container Lambdas
        # CloudWatch Logs are still available for monitoring

        # ========================================
        # Verification Workflow Lambda (Orchestrator)
        # ========================================
        workflow_log_group = logs.LogGroup(
            self, 'WorkflowLogGroup',
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )

        self.verification_workflow = _lambda.Function(
            self, "WorkflowFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="verification_workflow.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(300),  # 5 minutes to allow for validator execution
            memory_size=512,
            log_group=workflow_log_group,
            architecture=_lambda.Architecture.ARM_64,
            description="Orchestrates the complete verification workflow",
            environment={
                "POWERTOOLS_SERVICE_NAME": "VerificationWorkflow",
                "POWERTOOLS_METRICS_NAMESPACE": "MedicineVerification",
                "LOG_LEVEL": "INFO",
                "IMAGE_PROCESSOR_ARN": self.image_processor.function_arn,
                "NAFDAC_VALIDATOR_ARN": self.nafdac_validator_alias.function_arn
            },
            layers=[layer]
        )
        
        # Grant permissions to invoke other Lambdas
        self.image_processor.grant_invoke(self.verification_workflow)
        self.nafdac_validator_alias.grant_invoke(self.verification_workflow)
        
        # Grant CloudWatch PutMetricData for geolocation custom metrics
        self.verification_workflow.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )
        
        # Add CloudWatch Insights permissions
        self.verification_workflow.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('CloudWatchLambdaInsightsExecutionRolePolicy')
        )

        # Expose log groups for monitoring dashboard
        self.image_processor_log_group = image_processor_log_group
        self.nafdac_validator_log_group = validator_log_group
        self.verification_workflow_log_group = workflow_log_group
