from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
)
from constructs import Construct

DOMAIN_NAME = "nafdac.echefulouis.com"


class FrontendStack(Stack):
    def __init__(self, scope: Construct, id: str, api_url: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Look up the hosted zone in Account B
        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone",
            domain_name=DOMAIN_NAME,
        )

        # ACM certificate — must be in us-east-1 for CloudFront
        certificate = acm.DnsValidatedCertificate(
            self, "SiteCertificate",
            domain_name=DOMAIN_NAME,
            hosted_zone=hosted_zone,
            region="us-east-1",
        )

        bucket = s3.Bucket(
            self,
            "DeepFakeDrugWebsite",
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        s3deploy.BucketDeployment(
            self,
            "Deploy-the-front-end",
            sources=[s3deploy.Source.asset("frontend/dist")],
            destination_bucket=bucket,
        )

        distribution = cloudfront.Distribution(
            self,
            "CloudfrontSite",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            domain_names=[DOMAIN_NAME],
            certificate=certificate,
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        # Route 53 A record pointing to CloudFront
        route53.ARecord(
            self, "SiteAliasRecord",
            zone=hosted_zone,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )

        # Expose distribution for monitoring dashboard
        self.distribution = distribution

        CfnOutput(self, "SiteURL", value=f"https://{DOMAIN_NAME}")
        CfnOutput(self, "CloudFrontURL", value=distribution.distribution_domain_name)
        CfnOutput(self, "CloudFrontDistributionId", value=distribution.distribution_id)
