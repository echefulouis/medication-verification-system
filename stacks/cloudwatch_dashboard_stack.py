from aws_cdk import (
    Stack,
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_logs as logs,
)
from constructs import Construct


class CloudWatchDashboardStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        image_processor: _lambda.IFunction,
        nafdac_validator: _lambda.IFunction,
        verification_workflow: _lambda.IFunction,
        api: apigateway.RestApi,
        verification_table: dynamodb.Table,
        image_bucket: s3.Bucket,
        distribution: cloudfront.Distribution,
        image_processor_log_group: logs.ILogGroup,
        nafdac_validator_log_group: logs.ILogGroup,
        verification_workflow_log_group: logs.ILogGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store resource references
        self.image_processor = image_processor
        self.nafdac_validator = nafdac_validator
        self.verification_workflow = verification_workflow
        self.api = api
        self.verification_table = verification_table
        self.image_bucket = image_bucket
        self.distribution = distribution
        self.image_processor_log_group = image_processor_log_group
        self.nafdac_validator_log_group = nafdac_validator_log_group
        self.verification_workflow_log_group = verification_workflow_log_group

        # Create the consolidated dashboard
        self.dashboard = cloudwatch.Dashboard(
            self,
            "MedicineVerificationDashboard",
            dashboard_name="MedicineVerification-Dashboard",
            default_interval=Duration.hours(6),
        )

        # Add widgets by service — ordered for readability
        self._create_geolocation_widgets()
        self._create_verification_metrics_widgets()
        self._create_lambda_widgets()
        self._create_api_gateway_widgets()
        self._create_dynamodb_widgets()
        self._create_s3_widgets()
        self._create_cloudfront_widgets()
        self._create_log_insights_widgets()
        self._create_alarms()

    def _create_lambda_widgets(self) -> None:
        """Create Lambda metric widgets for all 3 functions."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## Lambda",
                width=24,
                height=1,
            )
        )
        functions = [
            self.image_processor,
            self.nafdac_validator,
            self.verification_workflow,
        ]

        # Invocations widget (8 wide, 6 tall)
        invocations_widget = cloudwatch.GraphWidget(
            title="Lambda Invocations",
            width=8,
            height=6,
            left=[fn.metric_invocations(statistic="Sum") for fn in functions],
        )

        # Errors widget (8 wide, 6 tall)
        errors_widget = cloudwatch.GraphWidget(
            title="Lambda Errors",
            width=8,
            height=6,
            left=[fn.metric_errors(statistic="Sum") for fn in functions],
        )

        # Throttles widget (8 wide, 6 tall)
        throttles_widget = cloudwatch.GraphWidget(
            title="Lambda Throttles",
            width=8,
            height=6,
            left=[fn.metric_throttles(statistic="Sum") for fn in functions],
        )

        # Concurrent Executions widget (12 wide, 6 tall)
        concurrent_widget = cloudwatch.GraphWidget(
            title="Lambda Concurrent Executions",
            width=12,
            height=6,
            left=[
                fn.metric("ConcurrentExecutions", statistic="Maximum")
                for fn in functions
            ],
        )

        # Duration widget (12 wide, 6 tall) — Avg, p50, p90, p99 for each function
        duration_metrics = []
        for fn in functions:
            duration_metrics.append(fn.metric_duration(statistic="Average"))
            duration_metrics.append(fn.metric_duration(statistic="p50"))
            duration_metrics.append(fn.metric_duration(statistic="p90"))
            duration_metrics.append(fn.metric_duration(statistic="p99"))

        duration_widget = cloudwatch.GraphWidget(
            title="Lambda Duration",
            width=12,
            height=6,
            left=duration_metrics,
        )

        # Error Rate widget (24 wide, 6 tall) — math expression per function
        error_rate_metrics = []
        for i, fn in enumerate(functions):
            error_rate_metrics.append(
                cloudwatch.MathExpression(
                    expression=f"(errors{i} / invocations{i}) * 100",
                    using_metrics={
                        f"errors{i}": fn.metric_errors(statistic="Sum"),
                        f"invocations{i}": fn.metric_invocations(statistic="Sum"),
                    },
                    label=f"{fn.node.id} Error Rate (%)",
                )
            )

        error_rate_widget = cloudwatch.GraphWidget(
            title="Lambda Error Rate",
            width=24,
            height=6,
            left=error_rate_metrics,
        )

        # Row 1: Invocations | Errors | Throttles
        self.dashboard.add_widgets(invocations_widget, errors_widget, throttles_widget)
        # Row 2: Duration | Concurrent Executions
        self.dashboard.add_widgets(duration_widget, concurrent_widget)
        # Row 3: Error Rate (full width)
        self.dashboard.add_widgets(error_rate_widget)

    def _create_api_gateway_widgets(self) -> None:
        """Create API Gateway metric widgets."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## API Gateway",
                width=24,
                height=1,
            )
        )
        # Request Count widget (8 wide, 6 tall)
        request_count_widget = cloudwatch.GraphWidget(
            title="API Requests",
            width=8,
            height=6,
            left=[self.api.metric_count(statistic="Sum")],
        )

        # 4xx Errors widget (8 wide, 6 tall)
        client_error_widget = cloudwatch.GraphWidget(
            title="API 4xx Errors",
            width=8,
            height=6,
            left=[self.api.metric_client_error(statistic="Sum")],
        )

        # 5xx Errors widget (8 wide, 6 tall)
        server_error_widget = cloudwatch.GraphWidget(
            title="API 5xx Errors",
            width=8,
            height=6,
            left=[self.api.metric_server_error(statistic="Sum")],
        )

        # Latency widget (12 wide, 6 tall) — Average, p50, p90, p99
        latency_widget = cloudwatch.GraphWidget(
            title="API Latency",
            width=12,
            height=6,
            left=[
                self.api.metric_latency(statistic="Average"),
                self.api.metric_latency(statistic="p50"),
                self.api.metric_latency(statistic="p90"),
                self.api.metric_latency(statistic="p99"),
            ],
        )

        # Integration Latency widget (12 wide, 6 tall) — Average, p50, p90, p99
        integration_latency_widget = cloudwatch.GraphWidget(
            title="API Integration Latency",
            width=12,
            height=6,
            left=[
                self.api.metric_integration_latency(statistic="Average"),
                self.api.metric_integration_latency(statistic="p50"),
                self.api.metric_integration_latency(statistic="p90"),
                self.api.metric_integration_latency(statistic="p99"),
            ],
        )

        # Row 4: API Requests (8) | API 4xx (8) | API 5xx (8)
        self.dashboard.add_widgets(request_count_widget, client_error_widget, server_error_widget)
        # Row 5: API Latency (12) | API Integration Latency (12)
        self.dashboard.add_widgets(latency_widget, integration_latency_widget)


    def _create_dynamodb_widgets(self) -> None:
        """Create DynamoDB metric widgets for the verification table."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## DynamoDB",
                width=24,
                height=1,
            )
        )
        table_name = self.verification_table.table_name

        # Read/Write Capacity widget (8 wide, 6 tall)
        rw_capacity_widget = cloudwatch.GraphWidget(
            title="DynamoDB Read/Write Capacity",
            width=8,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/DynamoDB",
                    metric_name="ConsumedReadCapacityUnits",
                    dimensions_map={"TableName": table_name},
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="AWS/DynamoDB",
                    metric_name="ConsumedWriteCapacityUnits",
                    dimensions_map={"TableName": table_name},
                    statistic="Sum",
                ),
            ],
        )

        # Throttled Requests widget (8 wide, 6 tall)
        throttled_widget = cloudwatch.GraphWidget(
            title="DynamoDB Throttled Requests",
            width=8,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/DynamoDB",
                    metric_name="ThrottledRequests",
                    dimensions_map={"TableName": table_name},
                    statistic="Sum",
                ),
            ],
        )

        # Successful Request Latency widget (8 wide, 6 tall)
        latency_widget = cloudwatch.GraphWidget(
            title="DynamoDB Request Latency",
            width=8,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/DynamoDB",
                    metric_name="SuccessfulRequestLatency",
                    dimensions_map={"TableName": table_name},
                    statistic="Average",
                ),
            ],
        )

        # Row 6: DynamoDB RCU/WCU (8) | DynamoDB Throttles (8) | DynamoDB Latency (8)
        self.dashboard.add_widgets(rw_capacity_widget, throttled_widget, latency_widget)

    def _create_s3_widgets(self) -> None:
        """Create S3 metric widgets for the image bucket."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## S3",
                width=24,
                height=1,
            )
        )
        bucket_name = self.image_bucket.bucket_name

        # Number of Objects widget (12 wide, 6 tall)
        objects_widget = cloudwatch.GraphWidget(
            title="S3 Number of Objects",
            width=12,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/S3",
                    metric_name="NumberOfObjects",
                    dimensions_map={
                        "BucketName": bucket_name,
                        "StorageType": "AllStorageTypes",
                    },
                    statistic="Average",
                    period=Duration.days(1),
                ),
            ],
        )

        # Bucket Size widget (12 wide, 6 tall)
        bucket_size_widget = cloudwatch.GraphWidget(
            title="S3 Bucket Size",
            width=12,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/S3",
                    metric_name="BucketSizeBytes",
                    dimensions_map={
                        "BucketName": bucket_name,
                        "StorageType": "StandardStorage",
                    },
                    statistic="Average",
                    period=Duration.days(1),
                ),
            ],
        )

        # Row 7: S3 Objects (12) | S3 Bucket Size (12)
        self.dashboard.add_widgets(objects_widget, bucket_size_widget)

    def _create_cloudfront_widgets(self) -> None:
        """Create CloudFront metric widgets for the distribution."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## CloudFront",
                width=24,
                height=1,
            )
        )
        distribution_id = self.distribution.distribution_id

        # Requests widget (8 wide, 6 tall)
        requests_widget = cloudwatch.GraphWidget(
            title="CloudFront Requests",
            width=8,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/CloudFront",
                    metric_name="Requests",
                    dimensions_map={
                        "DistributionId": distribution_id,
                        "Region": "Global",
                    },
                    statistic="Sum",
                ),
            ],
        )

        # Error Rate widget (8 wide, 6 tall)
        error_rate_widget = cloudwatch.GraphWidget(
            title="CloudFront Error Rate",
            width=8,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/CloudFront",
                    metric_name="TotalErrorRate",
                    dimensions_map={
                        "DistributionId": distribution_id,
                        "Region": "Global",
                    },
                    statistic="Average",
                ),
            ],
        )

        # Cache Hit Rate widget (8 wide, 6 tall)
        cache_hit_widget = cloudwatch.GraphWidget(
            title="CloudFront Cache Hit Rate",
            width=8,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/CloudFront",
                    metric_name="CacheHitRate",
                    dimensions_map={
                        "DistributionId": distribution_id,
                        "Region": "Global",
                    },
                    statistic="Average",
                ),
            ],
        )

        # Bytes Downloaded widget (24 wide, 6 tall)
        bytes_widget = cloudwatch.GraphWidget(
            title="CloudFront Bytes Downloaded",
            width=24,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="AWS/CloudFront",
                    metric_name="BytesDownloaded",
                    dimensions_map={
                        "DistributionId": distribution_id,
                        "Region": "Global",
                    },
                    statistic="Sum",
                ),
            ],
        )

        # Row 8: CloudFront Requests (8) | CloudFront Errors (8) | CloudFront Cache Hit (8)
        self.dashboard.add_widgets(requests_widget, error_rate_widget, cache_hit_widget)
        # Row 9: CloudFront Bytes Downloaded (24)
        self.dashboard.add_widgets(bytes_widget)

    def _create_log_insights_widgets(self) -> None:
        """Create CloudWatch Logs Insights query widgets."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## Logs",
                width=24,
                height=1,
            )
        )
        # Error Log Query widget (24 wide, 8 tall) — queries all 3 Lambda log groups
        error_log_widget = cloudwatch.LogQueryWidget(
            title="Error Logs (All Lambda Functions)",
            width=24,
            height=8,
            log_group_names=[
                self.image_processor_log_group.log_group_name,
                self.nafdac_validator_log_group.log_group_name,
                self.verification_workflow_log_group.log_group_name,
            ],
            query_lines=[
                "fields @timestamp, @message, @logStream, @log",
                'filter @message like /ERROR/ or level = "ERROR"',
                "sort @timestamp desc",
                "limit 50",
            ],
        )

        # Verification Trace Query widget (24 wide, 8 tall)
        verification_trace_widget = cloudwatch.LogQueryWidget(
            title="Verification Request Traces",
            width=24,
            height=8,
            log_group_names=[
                self.verification_workflow_log_group.log_group_name,
                self.image_processor_log_group.log_group_name,
            ],
            query_lines=[
                "fields @timestamp, @message, @logStream, @log",
                "filter @message like /verification_id/ or @message like /verificationId/",
                "sort @timestamp desc",
                "limit 50",
            ],
        )

        # Row 10: Error Logs Query (24)
        self.dashboard.add_widgets(error_log_widget)
        # Row 11: Verification Trace Query (24)
        self.dashboard.add_widgets(verification_trace_widget)

    def _create_geolocation_widgets(self) -> None:
        """Create geolocation metric widgets: Nigeria vs Other Countries."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## Geolocation",
                width=24,
                height=1,
            )
        )

        nigeria_metric = cloudwatch.Metric(
            namespace="MedicineVerification",
            metric_name="VerificationRequestByCountry",
            dimensions_map={"Country": "Nigeria"},
            statistic="Sum",
            period=Duration.minutes(5),
            label="Nigeria",
        )

        rest_of_world_metric = cloudwatch.Metric(
            namespace="MedicineVerification",
            metric_name="VerificationRequestByCountry",
            dimensions_map={"Country": "Other Countries"},
            statistic="Sum",
            period=Duration.minutes(5),
            label="Other Countries",
        )

        # Bar chart — Nigeria vs Other Countries counts (24h)
        self.dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Nigeria (24h)",
                width=6,
                height=4,
                metrics=[
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="VerificationRequestByCountry",
                        dimensions_map={"Country": "Nigeria"},
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
            ),
            cloudwatch.SingleValueWidget(
                title="Other Countries (24h)",
                width=6,
                height=4,
                metrics=[
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="VerificationRequestByCountry",
                        dimensions_map={"Country": "Other Countries"},
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="Nigeria vs Other Countries (Bar)",
                width=12,
                height=4,
                left=[
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="VerificationRequestByCountry",
                        dimensions_map={"Country": "Nigeria"},
                        statistic="Sum",
                        period=Duration.hours(24),
                        label="Nigeria",
                    ),
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="VerificationRequestByCountry",
                        dimensions_map={"Country": "Other Countries"},
                        statistic="Sum",
                        period=Duration.hours(24),
                        label="Other Countries",
                    ),
                ],
                view=cloudwatch.GraphWidgetView.BAR,
            ),
        )

        # Time-series line graph
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Requests: Nigeria vs Other Countries Over Time",
                width=24,
                height=6,
                left=[nigeria_metric, rest_of_world_metric],
            ),
        )

        # Recent Geolocated Requests — Log Insights query
        self.dashboard.add_widgets(
            cloudwatch.LogQueryWidget(
                title="Recent Geolocated Requests",
                width=24,
                height=8,
                log_group_names=[self.verification_workflow_log_group.log_group_name],
                query_lines=[
                    "fields @timestamp, @message, @logStream, @log",
                    'filter @message like /geolocation/',
                    "parse @message '\"geolocation\": *' as geo",
                    "sort @timestamp desc",
                    "limit 25",
                ],
            )
        )

    def _create_verification_metrics_widgets(self) -> None:
        """Create custom verification metrics widgets: image uploads vs manual inputs, NAFDAC not found."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## Verification Metrics",
                width=24,
                height=1,
            )
        )

        # Image Uploads vs Manual Inputs — combined on one graph
        combined_widget = cloudwatch.GraphWidget(
            title="Image Uploads vs Manual Inputs",
            width=12,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="MedicineVerification",
                    metric_name="ImageUpload",
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Image Uploads",
                ),
                cloudwatch.Metric(
                    namespace="MedicineVerification",
                    metric_name="ManualNafdacInput",
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Manual Inputs",
                ),
            ],
        )

        # NAFDAC Not Found metric
        not_found_widget = cloudwatch.GraphWidget(
            title="NAFDAC Number Not Found (OCR)",
            width=12,
            height=6,
            left=[
                cloudwatch.Metric(
                    namespace="MedicineVerification",
                    metric_name="NafdacNotFound",
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Not Found Count",
                ),
            ],
        )

        self.dashboard.add_widgets(combined_widget, not_found_widget)

        # Single number widgets for at-a-glance totals
        self.dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Image Uploads (24h)",
                width=8,
                height=4,
                metrics=[
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="ImageUpload",
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
            ),
            cloudwatch.SingleValueWidget(
                title="Manual NAFDAC Inputs (24h)",
                width=8,
                height=4,
                metrics=[
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="ManualNafdacInput",
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
            ),
            cloudwatch.SingleValueWidget(
                title="NAFDAC Not Found (24h)",
                width=8,
                height=4,
                metrics=[
                    cloudwatch.Metric(
                        namespace="MedicineVerification",
                        metric_name="NafdacNotFound",
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
            ),
        )

        # Log stream for NAFDAC not found events
        self.dashboard.add_widgets(
            cloudwatch.LogQueryWidget(
                title="NAFDAC Not Found — Log Details",
                width=24,
                height=6,
                log_group_names=[self.image_processor_log_group.log_group_name],
                query_lines=[
                    "fields @timestamp, @message, @logStream, @log",
                    'filter @message like /No NAFDAC found/',
                    "sort @timestamp desc",
                    "limit 25",
                ],
            )
        )

    def _create_alarms(self) -> None:
        """Create CloudWatch Alarms for critical thresholds."""
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## Alarms",
                width=24,
                height=1,
            )
        )
        self.alarms = []

        # --- Lambda Error Rate Alarms (Requirements 8.1, 8.2, 8.3) ---
        functions_config = [
            (self.image_processor, "ImageProcessor"),
            (self.nafdac_validator, "NAFDACValidator"),
            (self.verification_workflow, "VerificationWorkflow"),
        ]

        for fn, name in functions_config:
            error_rate = cloudwatch.MathExpression(
                expression="IF(invocations > 0, (errors / invocations) * 100, 0)",
                using_metrics={
                    "errors": fn.metric_errors(statistic="Sum"),
                    "invocations": fn.metric_invocations(statistic="Sum"),
                },
                label=f"{name} Error Rate",
                period=Duration.minutes(5),
            )

            alarm = error_rate.create_alarm(
                self,
                f"{name}ErrorRateAlarm",
                alarm_name=f"MedicineVerification-{name}-ErrorRate",
                threshold=5,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description=f"Alarm when {name} error rate exceeds 5%",
            )
            self.alarms.append(alarm)

        # --- Lambda Duration Alarms (Requirements 8.5, 8.6, 8.7) ---
        duration_config = [
            (self.image_processor, "ImageProcessor", 24000),      # 80% of 30s
            (self.nafdac_validator, "NAFDACValidator", 96000),     # 80% of 120s
            (self.verification_workflow, "VerificationWorkflow", 240000),  # 80% of 300s
        ]

        for fn, name, threshold_ms in duration_config:
            duration_alarm = fn.metric_duration(
                statistic="Average",
                period=Duration.minutes(5),
            ).create_alarm(
                self,
                f"{name}DurationAlarm",
                alarm_name=f"MedicineVerification-{name}-Duration",
                threshold=threshold_ms,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description=f"Alarm when {name} avg duration exceeds {threshold_ms}ms (80% of timeout)",
            )
            self.alarms.append(duration_alarm)

        # --- API 5xx Alarm (Requirement 8.4) ---
        api_5xx_alarm = self.api.metric_server_error(
            statistic="Sum",
            period=Duration.minutes(5),
        ).create_alarm(
            self,
            "Api5xxAlarm",
            alarm_name="MedicineVerification-API-5xxSpike",
            threshold=10,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description="Alarm when API 5xx errors exceed 10 in 5 minutes",
        )
        self.alarms.append(api_5xx_alarm)

        # --- DynamoDB Throttle Alarm (Requirement 8.8) ---
        dynamodb_throttle_alarm = cloudwatch.Metric(
            namespace="AWS/DynamoDB",
            metric_name="ThrottledRequests",
            dimensions_map={"TableName": self.verification_table.table_name},
            statistic="Sum",
            period=Duration.minutes(5),
        ).create_alarm(
            self,
            "DynamoDBThrottleAlarm",
            alarm_name="MedicineVerification-DynamoDB-Throttle",
            threshold=0,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description="Alarm when DynamoDB throttled requests exceed 0",
        )
        self.alarms.append(dynamodb_throttle_alarm)

        # --- Alarm Status Widget (Requirement 8.9) ---
        alarm_status_widget = cloudwatch.AlarmStatusWidget(
            title="Alarm Status",
            width=24,
            height=4,
            alarms=self.alarms,
        )
        # Row 12: Alarm Status (24)
        self.dashboard.add_widgets(alarm_status_widget)
