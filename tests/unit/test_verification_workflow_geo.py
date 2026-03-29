"""
Unit tests for geolocation integration in verification_workflow.py.

Tests cover:
- resolve_geolocation is called with the raw event
- CloudWatch metrics are emitted with correct namespace, metric names, and dimensions
- Metric emission failures don't block the verification workflow
- NAFDAC Validator payload includes geolocation data
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# Add lambda directory to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda'))

# Set required env vars before importing the module
os.environ.setdefault('IMAGE_PROCESSOR_ARN', 'arn:aws:lambda:us-east-1:123456789012:function:image-processor')
os.environ.setdefault('NAFDAC_VALIDATOR_ARN', 'arn:aws:lambda:us-east-1:123456789012:function:nafdac-validator')


SAMPLE_GEO_DATA = {
    "country_code": "NG",
    "country_name": "Nigeria",
    "region": "Lagos",
    "source_ip": "102.89.23.45",
    "resolution_method": "cloudfront_header",
}

SAMPLE_EVENT = {
    "body": json.dumps({"image": "base64data"}),
    "headers": {
        "CloudFront-Viewer-Country": "NG",
        "CloudFront-Viewer-Country-Region": "Lagos",
    },
    "requestContext": {"identity": {"sourceIp": "102.89.23.45"}},
}


def _make_payload_reader(payload_dict):
    """Create a mock Payload object with a read() method returning JSON bytes."""
    mock_payload = MagicMock()
    mock_payload.read.return_value = json.dumps(payload_dict).encode()
    return mock_payload


def _image_processor_success():
    return {
        "Payload": _make_payload_reader({
            "statusCode": 200,
            "body": json.dumps({
                "nafdacNumber": "A4-1650",
                "imageKey": "images/test.jpg",
            }),
        })
    }


def _validator_success():
    return {
        "Payload": _make_payload_reader({
            "statusCode": 200,
            "body": json.dumps({"verificationId": "abc-123", "validationResult": {"status": "valid"}}),
        })
    }


@patch('verification_workflow.resolve_geolocation', return_value=SAMPLE_GEO_DATA)
@patch('verification_workflow.cloudwatch_client')
@patch('verification_workflow.lambda_client')
def test_emits_cloudwatch_metrics_with_correct_data(mock_lambda, mock_cw, mock_geo):
    """Validates: Requirements 3.1, 3.2, 3.3 — correct metric names, dimensions, values."""
    from verification_workflow import handler

    mock_lambda.invoke.side_effect = [_image_processor_success(), _validator_success()]

    handler(SAMPLE_EVENT, MagicMock())

    mock_cw.put_metric_data.assert_called_once()
    call_kwargs = mock_cw.put_metric_data.call_args[1]

    assert call_kwargs['Namespace'] == 'MedicineVerification'
    metrics = call_kwargs['MetricData']
    assert len(metrics) == 2

    country_metric = metrics[0]
    assert country_metric['MetricName'] == 'VerificationRequestByCountry'
    assert country_metric['Dimensions'] == [{'Name': 'Country', 'Value': 'Nigeria'}]
    assert country_metric['Value'] == 1
    assert country_metric['Unit'] == 'Count'

    region_metric = metrics[1]
    assert region_metric['MetricName'] == 'VerificationRequestByRegion'
    assert region_metric['Dimensions'] == [{'Name': 'Region', 'Value': 'Lagos'}]
    assert region_metric['Value'] == 1
    assert region_metric['Unit'] == 'Count'


@patch('verification_workflow.resolve_geolocation', return_value=SAMPLE_GEO_DATA)
@patch('verification_workflow.cloudwatch_client')
@patch('verification_workflow.lambda_client')
def test_metric_failure_does_not_block_workflow(mock_lambda, mock_cw, mock_geo):
    """Validates: Requirement 5.2 — metric emission failure is non-blocking."""
    from verification_workflow import handler

    mock_cw.put_metric_data.side_effect = Exception("CloudWatch unavailable")
    mock_lambda.invoke.side_effect = [_image_processor_success(), _validator_success()]

    result = handler(SAMPLE_EVENT, MagicMock())

    # Workflow should still succeed despite metric failure
    assert result['statusCode'] == 200


@patch('verification_workflow.resolve_geolocation', return_value=SAMPLE_GEO_DATA)
@patch('verification_workflow.cloudwatch_client')
@patch('verification_workflow.lambda_client')
def test_validator_payload_includes_geolocation(mock_lambda, mock_cw, mock_geo):
    """Validates: Requirement 5.2 — downstream payload includes geolocation."""
    from verification_workflow import handler

    mock_lambda.invoke.side_effect = [_image_processor_success(), _validator_success()]

    handler(SAMPLE_EVENT, MagicMock())

    # Second invoke call is the NAFDAC Validator
    validator_call = mock_lambda.invoke.call_args_list[1]
    validator_payload = json.loads(validator_call[1]['Payload'])

    assert 'geolocation' in validator_payload
    assert validator_payload['geolocation'] == SAMPLE_GEO_DATA


@patch('verification_workflow.resolve_geolocation', return_value=SAMPLE_GEO_DATA)
@patch('verification_workflow.cloudwatch_client')
@patch('verification_workflow.lambda_client')
def test_resolve_geolocation_called_with_raw_event(mock_lambda, mock_cw, mock_geo):
    """Validates: Requirement 3.1 — geolocation resolved from the original event."""
    from verification_workflow import handler

    mock_lambda.invoke.side_effect = [_image_processor_success(), _validator_success()]

    handler(SAMPLE_EVENT, MagicMock())

    mock_geo.assert_called_once_with(SAMPLE_EVENT)


@patch('verification_workflow.resolve_geolocation')
@patch('verification_workflow.cloudwatch_client')
@patch('verification_workflow.lambda_client')
def test_unknown_geo_still_emits_metrics(mock_lambda, mock_cw, mock_geo):
    """Validates: Requirements 3.1, 3.2 — metrics emitted even with Unknown geo."""
    from verification_workflow import handler

    unknown_geo = {
        "country_code": "Unknown",
        "country_name": "Unknown",
        "region": "Unknown",
        "source_ip": "Unknown",
        "resolution_method": "unknown",
    }
    mock_geo.return_value = unknown_geo
    mock_lambda.invoke.side_effect = [_image_processor_success(), _validator_success()]

    handler(SAMPLE_EVENT, MagicMock())

    call_kwargs = mock_cw.put_metric_data.call_args[1]
    metrics = call_kwargs['MetricData']
    assert metrics[0]['Dimensions'] == [{'Name': 'Country', 'Value': 'Unknown'}]
    assert metrics[1]['Dimensions'] == [{'Name': 'Region', 'Value': 'Unknown'}]
