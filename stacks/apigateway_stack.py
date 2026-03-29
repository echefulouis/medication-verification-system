from aws_cdk import (
    Stack,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_lambda as _lambda
)
from constructs import Construct

class ApiGatewayStack(Stack):

    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        image_processor: _lambda.IFunction = None,
        nafdac_validator: _lambda.IFunction = None,
        verification_workflow: _lambda.IFunction = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.api = apigateway.RestApi(
            self, "MedicineVerificationAPI",
            rest_api_name="Medicine Verification API",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                tracing_enabled=True,
                data_trace_enabled=True,
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # Create /process-image endpoint for image processing and OCR
        if image_processor:
            process_image_resource = self.api.root.add_resource("process-image")
            process_image_integration = apigateway.LambdaIntegration(
                image_processor,
                proxy=True
            )
            process_image_resource.add_method("POST", process_image_integration)
        
        # Create /validate endpoint for NAFDAC number validation
        if nafdac_validator:
            validate_resource = self.api.root.add_resource("validate")
            validate_integration = apigateway.LambdaIntegration(
                nafdac_validator,
                proxy=True
            )
            validate_resource.add_method("POST", validate_integration)
        
        # Create /verify endpoint for complete workflow (recommended)
        if verification_workflow:
            verify_resource = self.api.root.add_resource("verify")
            verify_integration = apigateway.LambdaIntegration(
                verification_workflow,
                proxy=True
            )
            verify_resource.add_method("POST", verify_integration)
        
        # Output API endpoint
        CfnOutput(
            self, "ApiEndpoint",
            value=self.api.url,
            description="API Gateway endpoint URL"
        )