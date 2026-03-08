# AWS Setup Guide — Content Delivery API

Complete step-by-step instructions to deploy this project entirely on AWS.

**Services used**: S3, RDS PostgreSQL, CloudFront, EC2, IAM

**Estimated setup time**: 30–45 minutes

**Prerequisites**:
- AWS account (free tier works for testing)
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed
- Docker installed on your EC2 or local machine
- Git

---

## Step 1 — Configure AWS CLI

```bash
aws configure
```

Enter when prompted:
```
AWS Access Key ID:     [your root or admin IAM key]
AWS Secret Access Key: [your secret]
Default region:        us-east-1
Default output:        json
```

Verify it works:
```bash
aws sts get-caller-identity
```

---

## Step 2 — Create S3 Bucket

```bash
# Create the bucket (replace YOUR_BUCKET_NAME, keep globally unique)
aws s3api create-bucket \
  --bucket YOUR_BUCKET_NAME \
  --region us-east-1

# Block ALL public access (API proxies content — bucket stays private)
aws s3api put-public-access-block \
  --bucket YOUR_BUCKET_NAME \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket YOUR_BUCKET_NAME \
  --versioning-configuration Status=Enabled

echo "S3 bucket created: YOUR_BUCKET_NAME"
```

---

## Step 3 — Create IAM User & Policy for the App

```bash
# Create the IAM user
aws iam create-user --user-name cdn-api-user

# Create the access key (COPY THESE — only shown once)
aws iam create-access-key --user-name cdn-api-user
```

> **Save the `AccessKeyId` and `SecretAccessKey` from the output above.**

Now attach the policy. First, edit `scripts/iam_policy.json` and replace:
- `YOUR_BUCKET_NAME` with your actual bucket name
- `YOUR_ACCOUNT_ID` with your AWS account ID (`aws sts get-caller-identity --query Account --output text`)
- `YOUR_DISTRIBUTION_ID` with your CloudFront distribution ID (you'll get this in Step 5 — come back to update)

```bash
# Create the policy
aws iam create-policy \
  --policy-name CdnApiPolicy \
  --policy-document file://scripts/iam_policy.json

# Attach it to the user (replace YOUR_ACCOUNT_ID)
aws iam attach-user-policy \
  --user-name cdn-api-user \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/CdnApiPolicy

echo "IAM user and policy created"
```

---

## Step 4 — Create RDS PostgreSQL Database

```bash
# Create a DB subnet group first (use default VPC subnets)
# Get your default VPC subnets
aws ec2 describe-subnets \
  --filters "Name=default-for-az,Values=true" \
  --query "Subnets[*].SubnetId" \
  --output text

# Create the DB subnet group (replace SUBNET_1, SUBNET_2 with your subnet IDs)
aws rds create-db-subnet-group \
  --db-subnet-group-name cdn-db-subnet-group \
  --db-subnet-group-description "CDN API DB Subnet Group" \
  --subnet-ids SUBNET_1 SUBNET_2

# Create the RDS PostgreSQL instance (db.t3.micro = free tier eligible)
aws rds create-db-instance \
  --db-instance-identifier cdn-api-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.6 \
  --master-username cdnuser \
  --master-user-password CHANGE_ME_STRONG_PASSWORD \
  --db-name cdndb \
  --allocated-storage 20 \
  --db-subnet-group-name cdn-db-subnet-group \
  --publicly-accessible \
  --backup-retention-period 7 \
  --no-multi-az
```

Wait for it to be available (~5 minutes):
```bash
aws rds wait db-instance-available --db-instance-identifier cdn-api-db
echo "RDS is ready"
```

Get the endpoint:
```bash
aws rds describe-db-instances \
  --db-instance-identifier cdn-api-db \
  --query "DBInstances[0].Endpoint.Address" \
  --output text
```

> **Save this endpoint** — you'll use it in `DATABASE_URL`.

**Important**: Open port 5432 in the RDS security group so your EC2 / local machine can connect:
```bash
# Get the security group ID attached to the RDS instance
SG_ID=$(aws rds describe-db-instances \
  --db-instance-identifier cdn-api-db \
  --query "DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId" \
  --output text)

# Allow PostgreSQL from anywhere (restrict to your EC2 IP in production)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 5432 \
  --cidr 0.0.0.0/0
```

---

## Step 5 — Create CloudFront Distribution

Go to the AWS Console → CloudFront → **Create distribution** (CLI shown below):

```bash
# Get your EC2 public IP or DNS first (Step 6) — come back to this if deploying EC2
# For now, you can use your local IP or skip and do after Step 6

aws cloudfront create-distribution \
  --distribution-config '{
    "CallerReference": "cdn-api-dist-1",
    "Comment": "CDN API Distribution",
    "DefaultCacheBehavior": {
      "TargetOriginId": "cdn-api-origin",
      "ViewerProtocolPolicy": "redirect-to-https",
      "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
      "OriginRequestPolicyId": "b689b0a8-53d0-40ab-baf2-68738e2966ac",
      "AllowedMethods": {
        "Quantity": 7,
        "Items": ["GET","HEAD","OPTIONS","PUT","POST","PATCH","DELETE"],
        "CachedMethods": {"Quantity": 2,"Items": ["GET","HEAD"]}
      }
    },
    "Origins": {
      "Quantity": 1,
      "Items": [{
        "Id": "cdn-api-origin",
        "DomainName": "YOUR_EC2_PUBLIC_DNS",
        "CustomOriginConfig": {
          "HTTPPort": 3000,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "http-only"
        },
        "CustomHeaders": {
          "Quantity": 1,
          "Items": [{
            "HeaderName": "X-CDN-Secret",
            "HeaderValue": "YOUR_CDN_SECRET"
          }]
        }
      }]
    },
    "Enabled": true,
    "HttpVersion": "http2"
  }'
```

> **Save the `Id` (Distribution ID) and `DomainName` from the output.**

Get the distribution ID via CLI:
```bash
aws cloudfront list-distributions \
  --query "DistributionList.Items[0].Id" \
  --output text
```

---

## Step 6 — Launch EC2 Instance & Deploy App

### Launch EC2 (Amazon Linux 2023, t2.micro = free tier)

```bash
# Get the latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-*-x86_64" \
  --query "Images | sort_by(@, &CreationDate) | [-1].ImageId" \
  --output text)

echo "Using AMI: $AMI_ID"

# Create a security group for EC2
aws ec2 create-security-group \
  --group-name cdn-api-sg \
  --description "Security group for CDN API EC2"

SG_ID=$(aws ec2 describe-security-groups \
  --group-names cdn-api-sg \
  --query "SecurityGroups[0].GroupId" \
  --output text)

# Allow SSH (port 22) and app (port 3000)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22   --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 3000 --cidr 0.0.0.0/0

# Launch instance (replace YOUR_KEY_PAIR with your EC2 key pair name)
aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t2.micro \
  --key-name YOUR_KEY_PAIR \
  --security-group-ids $SG_ID \
  --count 1 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=cdn-api}]'
```

Wait for EC2 to be running:
```bash
aws ec2 wait instance-running --filters "Name=tag:Name,Values=cdn-api"

# Get the public DNS
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=cdn-api" \
  --query "Reservations[0].Instances[0].PublicDnsName" \
  --output text
```

### SSH into EC2 and Install Docker

```bash
ssh -i YOUR_KEY_PAIR.pem ec2-user@YOUR_EC2_PUBLIC_DNS

# On EC2:
sudo yum update -y
sudo yum install docker git -y
sudo service docker start
sudo usermod -a -G docker ec2-user
# Log out and back in for group change to take effect
exit
ssh -i YOUR_KEY_PAIR.pem ec2-user@YOUR_EC2_PUBLIC_DNS
```

### Clone and Configure the App on EC2

```bash
# On EC2:
git clone https://github.com/YOUR_USERNAME/aws-content-delivery-api.git
cd aws-content-delivery-api

# Create .env from production template
cp .env.production.example .env
nano .env    # Or: vi .env
```

Fill in `.env` with your actual values:
```env
DATABASE_URL=postgresql://cdnuser:CHANGE_ME_STRONG_PASSWORD@YOUR_RDS_ENDPOINT:5432/cdndb
S3_ENDPOINT_URL=                                  # leave blank for real AWS S3
S3_BUCKET_NAME=YOUR_BUCKET_NAME
AWS_ACCESS_KEY_ID=YOUR_IAM_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=YOUR_IAM_SECRET_KEY
AWS_REGION=us-east-1
CDN_ENABLED=true
CDN_SECRET=YOUR_CDN_SECRET
CLOUDFRONT_DISTRIBUTION_ID=YOUR_DISTRIBUTION_ID
ORIGIN_SHIELD_ENABLED=true
TOKEN_TTL_SECONDS=3600
```

### Run the App

```bash
# On EC2 — production mode (no MinIO/postgres containers):
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker logs cdn_app_prod -f
```

You should see:
```
[migrate] all migrations complete.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:3000
```

---

## Step 7 — Update IAM Policy with CloudFront Distribution ID

```bash
# Edit scripts/iam_policy.json — replace YOUR_DISTRIBUTION_ID with real ID
# Then update the policy:
aws iam create-policy-version \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/CdnApiPolicy \
  --policy-document file://scripts/iam_policy.json \
  --set-as-default
```

---

## Step 8 — Verify Everything Works

```bash
# Health check via CloudFront domain
curl https://YOUR_CLOUDFRONT_DOMAIN/health
# → {"status":"ok"}

# Upload a file
curl -X POST \
  -F "file=@/path/to/test.jpg" \
  https://YOUR_CLOUDFRONT_DOMAIN/assets/upload

# Download — first request (200 OK, CloudFront MISS)
curl -v https://YOUR_CLOUDFRONT_DOMAIN/assets/{id}/download
# Look for: X-Cache: Miss from cloudfront

# Download — second request (CloudFront HIT, no origin call)
curl -v https://YOUR_CLOUDFRONT_DOMAIN/assets/{id}/download
# Look for: X-Cache: Hit from cloudfront

# Conditional GET with ETag — 304
curl -v -H 'If-None-Match: "paste-etag-here"' \
  https://YOUR_CLOUDFRONT_DOMAIN/assets/{id}/download
# Expected: HTTP/2 304

# Publish new version
curl -X POST \
  -F "file=@/path/to/test-v2.jpg" \
  https://YOUR_CLOUDFRONT_DOMAIN/assets/{id}/publish
# CloudFront invalidation fires automatically

# Versioned immutable URL (1-year cache)
curl -v https://YOUR_CLOUDFRONT_DOMAIN/assets/public/{version_id}
# Cache-Control: public, max-age=31536000, immutable
```

---

## Step 9 — Run Tests & Benchmark Against AWS

```bash
# On EC2 (points at the running app):
docker-compose -f docker-compose.prod.yml run --rm app \
  pytest tests/ -v

# Benchmark against live AWS
BENCHMARK_URL=https://YOUR_CLOUDFRONT_DOMAIN \
  docker-compose -f docker-compose.prod.yml run --rm app \
  python scripts/run_benchmark.py
```

---

## Summary — What Gets Created

| AWS Service | Resource | Purpose |
|---|---|---|
| **S3** | `YOUR_BUCKET_NAME` | Private binary asset storage |
| **RDS** | `cdn-api-db` (PostgreSQL 15) | Asset metadata, versions, tokens |
| **IAM** | `cdn-api-user` + `CdnApiPolicy` | Least-privilege app credentials |
| **CloudFront** | Distribution | CDN edge caching + origin shield |
| **EC2** | `cdn-api` (t2.micro) | FastAPI app server |

---

## Architecture on AWS

```
Internet → CloudFront (edge cache)
               │
               │ X-CDN-Secret header added
               ▼
          EC2 t2.micro (Docker + FastAPI)
               │                │
               ▼                ▼
           RDS PostgreSQL    AWS S3
           (metadata)        (binary content)
```

---

## Clean Up (Avoid Charges)

When done testing:
```bash
aws ec2 terminate-instances --instance-ids YOUR_INSTANCE_ID
aws rds delete-db-instance --db-instance-identifier cdn-api-db --skip-final-snapshot
aws s3 rb s3://YOUR_BUCKET_NAME --force
aws cloudfront delete-distribution --id YOUR_DIST_ID --if-match YOUR_ETAG
aws iam detach-user-policy --user-name cdn-api-user --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/CdnApiPolicy
aws iam delete-access-key --user-name cdn-api-user --access-key-id YOUR_KEY_ID
aws iam delete-user --user-name cdn-api-user
aws iam delete-policy --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/CdnApiPolicy
```
