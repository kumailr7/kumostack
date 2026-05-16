# Tutorials

Step-by-step guides for using KumoStack with real AWS services — all running locally, no AWS account needed.

## Available tutorials

| Tutorial | Services | Time |
|---|---|---|
| [Getting Started](getting-started.md) | S3, Lambda, SQS | 10 min |
| [S3 — Object Storage](s3.md) | S3 | 15 min |
| [Lambda — Serverless Functions](lambda.md) | Lambda, IAM | 20 min |
| [RDS — Managed Databases](rds.md) | RDS (PostgreSQL), Secrets Manager | 20 min |
| [DynamoDB — NoSQL](dynamodb.md) | DynamoDB | 15 min |
| [SQS & SNS — Messaging](sqs-sns.md) | SQS, SNS | 20 min |
| [API Gateway](api-gateway.md) | API Gateway, Lambda | 25 min |

## Before you begin

All tutorials assume KumoStack is running:

```bash
docker compose up -d
```

And that you have either `awslocal` or `aws` CLI with endpoint override:

```bash
# Option A — awslocal wrapper (recommended)
awslocal s3 ls

# Option B — standard AWS CLI with endpoint
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
aws --endpoint-url http://localhost:4566 s3 ls
```
