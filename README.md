# NAFDAC Drug Verification System

> Helping Nigerians verify if their medicine is real — instantly, from their phone.

[![AWS](https://img.shields.io/badge/AWS-Serverless-orange)](https://aws.amazon.com)
[![React](https://img.shields.io/badge/React-19+-61dafb)](https://reactjs.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776ab)](https://www.python.org)
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
  <img src=".docs/image.png" alt="NAFDAC Drug Verification App" width="600" style="border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
</div>

---

## The Problem

Counterfeit and substandard medicines are a serious public health crisis in Nigeria. Fake drugs account for a significant portion of medicines in circulation — and most people have no easy way to check if what they are buying is genuine.

The official NAFDAC Greenbook exists, but it requires navigating a website, manually typing a registration number, and understanding what the results mean. Most people in markets and pharmacies simply do not do this check.

**The result**: people take medicines that may be fake, expired, or unregistered, putting their health at serious risk.

---

## What This App Does

This system makes drug verification as simple as taking a photo.

1. **Take a photo** of any medicine packaging
2. The app **reads the NAFDAC number** from the image automatically
3. It **checks the NAFDAC Greenbook** in real time
4. You get an instant result — **genuine or not found**

No technical knowledge needed. Works on any device with a camera and internet connection.

---

## Key Benefits

- **Fast** — results in under 10 seconds
- **Simple** — just upload a photo or type a number
- **Accurate** — checks directly against the official NAFDAC database
- **Free** — no cost to end users
- **Works anywhere** — accessible via browser, no app install needed
- **Handles unclear images** — AI fallback identifies the product name when the NAFDAC number is not readable

---

## How It Works

```
You upload a photo
       ↓
AI reads the NAFDAC number from the packaging
       ↓
System checks the official NAFDAC Greenbook database
       ↓
You see: product name, registration status, active ingredients
```

If the NAFDAC number is not visible in the photo, the AI identifies the product name instead and searches by name.

---

## Architecture Overview

The app runs entirely on AWS serverless infrastructure — scales automatically, costs nothing when idle, no servers to manage.

```
User (Browser)
    → CloudFront (CDN)
    → API Gateway
    → Verification Workflow Lambda
        → Image Processor Lambda  (OCR via Textract + AI via Bedrock)
        → NAFDAC Validator Lambda (scrapes Greenbook with Chrome/Selenium)
    → DynamoDB (stores results)
    → S3 (stores uploaded images)
```

| Layer | Technology | What it does |
|-------|-----------|--------------|
| Frontend | React + CloudFront | User interface, served globally via CDN |
| API | AWS API Gateway | Routes requests to the right Lambda |
| Image Processing | AWS Lambda + Textract | Reads NAFDAC number from photo |
| AI Fallback | AWS Bedrock (Claude) | Identifies product name when OCR fails |
| Validation | AWS Lambda + Selenium | Scrapes NAFDAC Greenbook live |
| Database | DynamoDB | Stores verification history (90-day TTL) |
| Storage | S3 | Stores uploaded images securely |
| Monitoring | CloudWatch | Logs, metrics, alarms, dashboard |

---

## Deploying the App

### Prerequisites

- AWS account with admin access
- AWS CLI configured (`aws configure`)
- Node.js 18+ 
- Python 3.12+
- Docker (for the Lambda container)
- AWS CDK: `npm install -g aws-cdk`

### Step 1 — Clone and install

```bash
git clone https://github.com/echefulouis/med-system-application.git
cd med-system-application

# Python dependencies
pip install uv && uv sync

# Frontend dependencies
cd frontend && npm install && cd ..
```

### Step 2 — Bootstrap CDK (first time only)

```bash
cdk bootstrap
```

### Step 3 — Deploy

```bash
./deploy.sh
```

This single script deploys everything: S3, DynamoDB, Lambda, API Gateway, React frontend, CloudFront, and the CloudWatch dashboard. The live URL is printed at the end.

### Step 4 — Custom Domain (optional)

Update `DOMAIN_NAME` in `stacks/frontend_stack.py` to your domain and ensure the hosted zone exists in Route 53.

---

## Test Images

The `test_images/` folder contains 220 real pharmaceutical product images (36–64KB each) used to validate the pipeline. A sample:

| Image | Format | NAFDAC Number | Product |
|-------|--------|---------------|---------|
| image1.jpeg | JPEG | 04-7951 | — |
| image104.jpeg | JPEG | 04-1426 | Diflucan 50mg Capsules |
| image107.jpeg | JPEG | 04-2450 | Glanil 5mg Caplet |
| image111.jpeg | JPEG | 04-0810 | Diabetmin Tablet 500mg |
| image114.jpeg | JPEG | 04-2853 | Amaryl 2mg Tablets |
| image116.jpeg | JPEG | A4-2608 | Diamet SR 1000mg Tablet |
| image122.jpeg | JPEG | B4-9698 | Vilget 50mg Tablet |
| image145.png | PNG | 04-9927 | Lonart-DS Tablets |
| image149.png | PNG | 04-9495 | P-Alaxin Tablets |
| image153.png | PNG | B4-2018 | Sumether 80/480 Tablets |
| image197.png | PNG | B4-1650 | Pocco Lisinopril 10 Tablet |
| image199.png | PNG | A4-5443 | Aldomet 250mg Tablets |

Images without a visible NAFDAC number fall back to AI product name extraction.

### Running the Test Suite

```bash
python -m tests.test_comprehensive_verification
```

Results and the generated report are saved to `tests/reports/`.

---

## Project Structure

```
medication-verification-system/
├── frontend/                 # React app (user interface)
├── lambda/                   # Backend Lambda functions
│   ├── image_processor.py        # OCR + image storage
│   ├── nafdac_validator_container.py  # Greenbook scraper (Docker)
│   ├── verification_workflow.py  # Orchestrates the full flow
│   └── Dockerfile                # Chrome + Selenium container
├── stacks/                   # AWS infrastructure (CDK)
│   ├── s3_stack.py
│   ├── dynamodb_stack.py
│   ├── lambda_stack.py
│   ├── apigateway_stack.py
│   ├── frontend_stack.py
│   └── cloudwatch_dashboard_stack.py
├── tests/
│   ├── test_comprehensive_verification.py
│   └── reports/              # Test results and reports
├── test_images/              # Sample pharmaceutical images
├── layer/                    # Shared Lambda layer
├── app.py                    # CDK entry point
├── deploy.sh                 # One-command deployment script
└── README.md
```

---

## Monitoring

A CloudWatch Dashboard (`MedicineVerification-Dashboard`) is deployed automatically and shows Lambda errors, API traffic, DynamoDB activity, CloudFront cache stats, and live error logs.

| Alarm | Triggers when |
|-------|--------------|
| Lambda Error Rate | Error rate > 5% over 10 minutes |
| Lambda Duration | Avg duration > 80% of timeout |
| API 5xx Spike | More than 10 server errors in 5 minutes |
| DynamoDB Throttle | Any throttled requests |

---

## Troubleshooting

**Deployment fails with permission error** — Run `aws sts get-caller-identity` to confirm credentials are valid.

**Lambda times out during validation** — The Greenbook scraper uses Chrome and can be slow. Check CloudWatch logs if it consistently fails.

**Frontend shows wrong API URL** — Check `frontend/.env` for `VITE_API_URL`. The deploy script sets this automatically.

**OCR returns no NAFDAC number** — Image may be blurry. The system falls back to AI product name extraction automatically.

---

## License

MIT — see [LICENSE](LICENSE) for details.

> This app is for verification purposes only. Always consult a healthcare professional for medical advice. NAFDAC Greenbook data is sourced from [greenbook.nafdac.gov.ng](https://greenbook.nafdac.gov.ng).
