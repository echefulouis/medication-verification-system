#!/bin/bash

# Exit on error and make pipelines fail if any command fails
set -e
set -o pipefail

# Create dist folder if it doesn't exist to avoid frontend deployment errors
mkdir -p frontend/dist
echo "temporary file" > frontend/dist/index.html

# Deploy infrastructure stacks (excluding frontend)
echo "Deploying infrastructure stacks..."
if ! cdk deploy MedicineVerificationS3Stack MedicineVerificationDynamoDBStack MedicineVerificationLambdaStack MedicineVerificationApiStack --require-approval never 2>&1 | tee deployment-output.txt; then
    echo "ERROR: Infrastructure deployment failed. Stopping deployment."
    exit 1
fi

# Extract API endpoint and create frontend .env file
echo "Extracting API endpoint..."
if ! {
    # Extract ApiEndpoint from CDK output and remove trailing slash
    API_ENDPOINT=$(grep "ApiEndpoint" deployment-output.txt | head -1 | sed 's/.*= *//' | sed 's|/$||' | tr -d ' ')
    echo "VITE_API_URL=${API_ENDPOINT}"
} > frontend/.env; then
    echo "ERROR: Failed to extract API endpoint. Stopping deployment."
    exit 1
fi

echo "API Endpoint: ${API_ENDPOINT}"

# Build and deploy frontend
echo "Building frontend..."
cd frontend

if ! npm install; then
    echo "ERROR: npm install failed. Stopping deployment."
    exit 1
fi

if ! npm run build; then
    echo "ERROR: Frontend build failed. Stopping deployment."
    exit 1
fi

cd ..

# Deploy frontend stack
echo "Deploying frontend to S3 + CloudFront..."
if ! cdk deploy MedicineVerificationFrontendStack --require-approval never 2>&1 | tee -a deployment-output.txt; then
    echo "ERROR: Frontend deployment failed. Stopping deployment."
    exit 1
fi

# Extract CloudFront Distribution ID and create invalidation
echo "Creating CloudFront invalidation..."
DISTRIBUTION_ID=$(grep "MedicineVerificationFrontendStack.CloudFrontDistributionId" deployment-output.txt | awk -F'=' '{print $2}' | tr -d ' ')

if [ -z "$DISTRIBUTION_ID" ]; then
    echo "WARNING: Could not extract CloudFront Distribution ID. Skipping invalidation."
else
    echo "Invalidating CloudFront distribution: $DISTRIBUTION_ID"
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text 2>&1)

    if [ $? -eq 0 ]; then
        echo "CloudFront invalidation created successfully. Invalidation ID: $INVALIDATION_ID"
        echo "Note: It may take a few minutes for the invalidation to complete."
    else
        echo "WARNING: Failed to create CloudFront invalidation: $INVALIDATION_ID"
        echo "You may need to manually invalidate the cache or wait for it to expire."
    fi
fi

# Deploy CloudWatch Dashboard stack
echo "Deploying CloudWatch Dashboard..."
if ! cdk deploy MedicineVerificationDashboardStack --require-approval never; then
    echo "ERROR: Dashboard deployment failed. Stopping deployment."
    exit 1
fi

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo "Check CloudFront URL in the output above."
echo ""
