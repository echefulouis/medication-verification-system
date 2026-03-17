# NAFDAC Drug Verification System

> A production-ready, serverless web application for verifying pharmaceutical products using NAFDAC registration numbers. Built with React and AWS cloud infrastructure.

[![AWS](https://img.shields.io/badge/AWS-Serverless-orange)](https://aws.amazon.com)
[![React](https://img.shields.io/badge/React-19+-61dafb)](https://reactjs.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776ab)](https://www.python.org)
[![CDK](https://img.shields.io/badge/AWS%20CDK-v2-ff9900)](https://aws.amazon.com/cdk)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

The NAFDAC Drug Verification System is an enterprise-grade application that helps consumers and healthcare professionals verify the authenticity of pharmaceutical products registered with Nigeria's National Agency for Food and Drug Administration and Control (NAFDAC). The system provides real-time verification through image recognition or manual NAFDAC number entry, with comprehensive product details and registration status.

**Live Demo**: [nafdac.echefulouis.com](https://nafdac.echefulouis.com/)

<div align="center">
  <img src=".docs/image.png" alt="Frontend Application" width="600" style="border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
</div>

### Key Capabilities

- **Dual Verification Modes**: Upload product images or manually enter NAFDAC registration numbers
- **AI-Powered OCR**: Automatic text extraction from product images using AWS Textract
- **Intelligent Product Recognition**: AWS Bedrock (Claude) for product name extraction when NAFDAC numbers aren't visible
- **Real-time Database Scraping**: Live verification against NAFDAC Greenbook
- **Scalable Infrastructure**: Serverless architecture that automatically scales with demand
- **Production Monitoring**: Built-in CloudWatch logging and tracing for observability

## Features

### Core Functionality

- **Image-Based Verification**: Upload photos of pharmaceutical products for automatic NAFDAC number extraction
- **Manual Verification**: Direct NAFDAC number entry for quick lookups
- **OCR Text Extraction**: AWS Textract automatically extracts text from product images
- **AI Product Recognition**: AWS Bedrock identifies product names when NAFDAC numbers aren't detected
- **Live NAFDAC Validation**: Real-time scraping of NAFDAC Greenbook database
- **Comprehensive Product Details**: Product name, active ingredients, category, registration number, and status
- **Visual Progress Tracking**: Real-time progress indicators during verification process
- **Verification History**: DynamoDB storage of all verification attempts with 90-day TTL

### Infrastructure Features

- **Serverless Architecture**: Zero infrastructure management overhead
- **Global CDN**: CloudFront distribution for worldwide low-latency access
- **Enterprise Security**: End-to-end encryption, IAM roles, and secure credential management
- **Comprehensive Logging**: CloudWatch logs with AWS Lambda Powertools
- **Cost Optimized**: Pay-per-use pricing with automatic scaling to zero
- **Automated Deployment**: One-click deployment with error handling and rollback capability

## Architecture

The application implements a modern serverless microservices architecture on AWS, designed for scalability, reliability, and operational excellence.

### Architecture Overview

The system follows a serverless microservices pattern with the following request flow:

1. **User → CloudFront/S3**: User opens the React app via CloudFront, which serves static content from an S3 bucket
2. **Frontend → API Gateway**: The frontend sends verification requests to the REST API in API Gateway
3. **API Gateway → Lambda**: API Gateway invokes Lambda functions based on the endpoint:
   - `/verify` - Complete workflow (recommended)
   - `/process-image` - Image processing and OCR only
   - `/validate` - NAFDAC validation only
4. **Verification Workflow**:
   - **Image Processor Lambda**: Stores image in S3, extracts NAFDAC number via Textract, or product name via Bedrock
   - **NAFDAC Validator Lambda**: Scrapes NAFDAC Greenbook using Selenium in Docker container
5. **Lambda → DynamoDB**: Lambda stores verification results and metadata in DynamoDB with 90-day TTL
6. **Lambda → S3**: Lambda saves uploaded images in the backend S3 bucket
7. **CloudWatch Logs**: CloudWatch captures detailed logs and traces for debugging and observability

### Architecture Components

#### Frontend Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **UI Framework** | React 19+ | Modern, component-based user interface |
| **Build Tool** | Vite | Fast development and optimized production builds |
| **CDN** | CloudFront | Global content delivery with edge caching |
| **Hosting** | S3 | Static website hosting with high availability |

#### API Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Gateway** | AWS API Gateway | RESTful API with request routing and throttling |
| **Workflow Orchestration** | AWS Lambda (Python) | Coordinates image processing and validation |
| **Image Processing** | AWS Lambda (Python) | OCR extraction and image storage |
| **NAFDAC Validation** | AWS Lambda (Docker) | Web scraping with Selenium and Chrome |
| **Runtime** | Python 3.12 | High-performance processing and API integration |

#### Storage Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Object Storage** | Amazon S3 | Secure image storage with encryption at rest |
| **Database** | Amazon DynamoDB | NoSQL database for verification results with GSI |
| **TTL Management** | DynamoDB TTL | Automatic cleanup of records after 90 days |

#### AI/ML Services

| Component | Technology | Purpose |
|-----------|------------|---------|
| **OCR** | AWS Textract | Text extraction from product images |
| **Product Recognition** | AWS Bedrock (Claude 3 Haiku) | Product name extraction when NAFDAC number not found |
| **Web Scraping** | Selenium + Chrome | Real-time NAFDAC Greenbook validation |

#### Observability Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Logging** | CloudWatch Logs | Centralized logging with retention policies |
| **Structured Logging** | AWS Lambda Powertools | Enhanced logging with context injection |
| **Tracing** | AWS X-Ray | Distributed tracing for performance analysis |

#### Security Features

- **Encryption**: Data encrypted at rest (S3, DynamoDB) and in transit (HTTPS/TLS)
- **Access Control**: IAM roles with least-privilege principles
- **Network Security**: VPC-ready architecture for enhanced network isolation
- **CORS Configuration**: Secure cross-origin resource sharing

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **AWS CLI** configured with appropriate credentials
- **Node.js** 18 or higher
- **Python** 3.12 or higher
- **AWS CDK** v2 installed globally (`npm install -g aws-cdk`)
- **Docker** (for local Lambda container testing)

### Installation Steps

1. **Clone the repository**

```bash
git clone <repository-url>
cd Nafdac
```

2. **Install Dependencies**

```bash
# Install Python dependencies (using uv)
uv sync

# Install frontend dependencies
cd frontend
npm install
cd ..
```

3. **Bootstrap AWS CDK** (first-time only)

```bash
cdk bootstrap
```

4. **Deploy Infrastructure**

```bash
./deploy.sh
```

The deployment script will:
- Deploy all AWS infrastructure stacks
- Build and deploy the frontend application
- Configure CloudFront distribution
- Create CloudWatch logging

5. **Access the Application**

After deployment, the CloudFront URL will be displayed in the output. The application will be accessible at:

```
https://<cloudfront-distribution-id>.cloudfront.net
```

### Local Development

To run the frontend locally for development:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` (or the port specified by Vite).

**Note**: For local development, you'll need to update the API endpoint in `frontend/.env`:

```bash
VITE_API_URL=https://your-api-gateway-url.amazonaws.com/prod
```

## Deployment

### Automated Deployment

The `deploy.sh` script provides a fully automated deployment process with comprehensive error handling:

```bash
./deploy.sh
```

#### Deployment Process

1. **Infrastructure Deployment**
   - S3 Stack (Image storage bucket)
   - DynamoDB Stack (Verification records database with GSI)
   - Lambda Stack (Serverless functions with container support)
   - API Gateway Stack (REST API endpoints)

2. **Frontend Build**
   - Dependency installation
   - Production build optimization
   - Environment variable configuration

3. **Frontend Deployment**
   - S3 bucket upload
   - CloudFront distribution update
   - CDN cache invalidation

4. **Verification**
   - Error checking at each stage
   - Deployment output logging
   - Rollback on failure



## Project Structure

```
Nafdac/
├── frontend/                 # React frontend application
│   ├── src/
│   │   ├── App.tsx          # Main application component
│   │   ├── App.css          # Application styles
│   │   └── main.tsx         # Application entry point
│   ├── public/              # Static assets
│   ├── dist/                # Production build (generated)
│   ├── package.json         # Node.js dependencies
│   └── vite.config.ts       # Vite configuration
├── lambda/                   # AWS Lambda functions
│   ├── image_processor.py   # Image upload and OCR handler
│   ├── nafdac_validator_container.py  # NAFDAC validation (Docker)
│   ├── verification_workflow.py       # Workflow orchestration
│   ├── Dockerfile           # Container image for Selenium
│   ├── .dockerignore        # Docker ignore patterns
│   └── requirements.txt     # Python dependencies
├── stacks/                   # AWS CDK infrastructure stacks
│   ├── __init__.py
│   ├── lambda_stack.py      # Lambda function definitions
│   ├── apigateway_stack.py  # API Gateway configuration
│   ├── frontend_stack.py    # Frontend deployment stack
│   ├── s3_stack.py          # S3 bucket definitions
│   ├── dynamodb_stack.py    # DynamoDB table definitions
│   └── nafdac_stack.py      # NAFDAC-specific resources
├── layer/                    # Lambda layers
│   └── layer.zip            # Python dependencies layer
├── tests/                    # Unit tests
├── app.py                    # CDK app entry point
├── deploy.sh                 # Deployment automation script
├── deployment-output.txt     # Deployment logs (generated)
├── cdk.json                  # CDK configuration
├── pyproject.toml            # Python project configuration
├── uv.lock                   # Python dependency lock file
└── README.md                 # This file
```

## Requirements

### System Requirements

- **Operating System**: macOS, Linux, or Windows (WSL)
- **AWS Account**: Active AWS account with appropriate permissions
- **Node.js**: Version 18.0.0 or higher
- **Python**: Version 3.12.0 or higher
- **AWS CLI**: Latest version configured with credentials
- **Docker**: For building Lambda container images


### Software Dependencies

- AWS CDK CLI: `npm install -g aws-cdk`
- Python dependencies: See `pyproject.toml`
- Node.js dependencies: See `frontend/package.json`
- Lambda layer dependencies: See `lambda/requirements.txt`


## Troubleshooting

### Common Issues

#### Deployment Failures

**Issue**: CDK deployment fails with permission errors

**Solution**:
- Verify AWS credentials: `aws sts get-caller-identity`
- Check IAM permissions for CDK deployment
- Ensure CDK bootstrap is complete: `cdk bootstrap`

**Issue**: Frontend build fails

**Solution**:
- Verify Node.js version: `node --version` (should be 18+)
- Clear npm cache: `npm cache clean --force`
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`

**Issue**: Docker image build fails for Lambda container

**Solution**:
- Ensure Docker is running: `docker ps`
- Check Docker disk space: `docker system df`
- Verify Dockerfile syntax in `lambda/Dockerfile`

#### Runtime Errors

**Issue**: Lambda function timeout during NAFDAC validation

**Solution**:
- Check CloudWatch logs: `/aws/lambda/nafdac_validator_function`
- Increase Lambda timeout in `lambda_stack.py` (current: 300s)
- Verify NAFDAC Greenbook website is accessible
- Check Selenium Chrome driver compatibility

**Issue**: OCR extraction returns no results

**Solution**:
- Verify image quality and resolution
- Check Textract service limits and quotas
- Review CloudWatch logs for Textract errors
- Ensure image is stored correctly in S3

**Issue**: Bedrock model invocation fails

**Solution**:
- Verify Bedrock model access in your AWS region
- Check IAM permissions for Bedrock
- Ensure Claude 3 Haiku model is enabled
- Review CloudWatch logs for specific error messages

**Issue**: API Gateway returns 502 errors

**Solution**:
- Verify Lambda function is deployed and healthy
- Check Lambda function logs in CloudWatch
- Verify API Gateway integration configuration
- Check CORS settings in `apigateway_stack.py`

**Issue**: Frontend cannot connect to API

**Solution**:
- Verify `frontend/.env` contains correct API endpoint
- Check CORS configuration in API Gateway
- Verify API Gateway deployment is complete
- Check browser console for specific error messages

### Getting Help

1. **Check Logs**: Review CloudWatch logs for detailed error information
   - Image Processor: `/aws/lambda/image_processor_function`
   - NAFDAC Validator: `/aws/lambda/nafdac_validator_function`
   - Workflow: `/aws/lambda/verification_workflow_function`

2. **Review Deployment Output**: Check `deployment-output.txt` for deployment errors

3. **Verify Configuration**: Ensure all environment variables are correctly configured

4. **Test Components**: Use manual testing procedures to verify API functionality

### Support Resources

- **CloudWatch Logs**: Check Lambda function logs for detailed error traces
- **Deployment Log**: `deployment-output.txt`
- **CDK Documentation**: [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- **AWS Textract**: [Textract Documentation](https://docs.aws.amazon.com/textract/)
- **AWS Bedrock**: [Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- **NAFDAC Greenbook**: [https://greenbook.nafdac.gov.ng/](https://greenbook.nafdac.gov.ng/)


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


---

**Note**: This application is for educational and verification purposes. Always consult with healthcare professionals for medical advice. The NAFDAC Greenbook data is sourced from the official NAFDAC website and is subject to their terms of use.
