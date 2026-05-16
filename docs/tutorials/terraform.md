# Terraform & tfstack

Provision KumoStack resources with Terraform — no real AWS account, no cloud cost. tfstack handles all the endpoint plumbing automatically, and Garage stores your state durably across restarts.

**Time:** ~20 minutes  
**Services:** S3, SQS, Lambda, DynamoDB, IAM  
**State backend:** Garage (S3-compatible, local)

---

## How it fits together

```
  Your .tf files
       │
       ▼
    tfstack        ← thin wrapper around terraform
       │ generates kumostack_providers_override.tf
       │ (redirects every AWS endpoint → localhost:4566)
       │ (cleans it up after terraform exits)
       │
       ├──► KumoStack :4566   ← AWS resources (S3, SQS, Lambda…)
       │
       └──► Garage     :3900  ← terraform.tfstate (durable, S3-compatible)
```

**tfstack** generates a temporary provider override file that points every AWS service endpoint at `localhost:4566`. You write normal Terraform — tfstack handles the redirect. You never need to manually configure `endpoints {}` blocks.

**Garage** is a self-hosted S3-compatible store that writes to disk. State stored in Garage survives `docker compose down`, unlike KumoStack's own S3 which is ephemeral by default.

---

## Prerequisites

- KumoStack stack running (`docker compose up -d`)
- `terraform` on your PATH (`brew install terraform` or [download](https://developer.hashicorp.com/terraform/install))
- `bin/tfstack` — no install needed, ships with the repo

```bash
# Add bin/ to PATH (add to ~/.zshrc or ~/.bashrc to make permanent)
export PATH="/path/to/kumostack/bin:$PATH"

# Verify
tfstack --version
# tfstack v1.0.0 / Terraform v1.x.x
```

!!! tip "No pip install required"
    `bin/tfstack` auto-bootstraps itself. On first run it finds `.venv` or runs
    `uv sync` to create one. No `pip install`, no virtual environment setup needed.

---

## 1. Create the Terraform state bucket in Garage

Garage persists state to disk. Before using it as a backend, create the bucket once:

```bash
# Create the bucket
docker exec kumostack-garage /garage bucket create terraform-state

# Grant the pre-configured key full access
docker exec kumostack-garage /garage bucket allow \
  --read --write --owner terraform-state \
  --key GK9ef5917d6d47e3bc0daae850

# Verify
docker exec kumostack-garage /garage bucket list
```

---

## 2. Write your Terraform config

Create a `main.tf` with the S3 backend pointing to Garage and the AWS provider pointing to KumoStack:

```hcl title="main.tf"
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Garage as S3 remote backend — state persists across KumoStack restarts
  backend "s3" {
    bucket = "terraform-state"
    key    = "myproject/terraform.tfstate"
    region = "us-east-1"

    endpoints = {
      s3 = "http://localhost:3900"   # Garage S3 API
    }

    # Local Garage credentials (from .env.example — not real AWS keys)
    access_key = "GK9ef5917d6d47e3bc0daae850"
    secret_key = "f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd"

    force_path_style            = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
  }
}

# Provider — tfstack auto-generates this override, but you can keep it explicit
provider "aws" {
  region     = "us-east-1"
  access_key = "test"
  secret_key = "test"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
}
```

!!! note "Provider endpoints block"
    When you run `tfstack`, it writes a `kumostack_providers_override.tf` that
    overrides every AWS service endpoint. You don't need to manually add
    `endpoints {}` to your provider block — tfstack does it for you.

---

## 3. Add resources

```hcl title="main.tf (continued)"
# S3 bucket
resource "aws_s3_bucket" "app_data" {
  bucket = "my-app-data"
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  versioning_configuration { status = "Enabled" }
}

# SQS queue with dead-letter queue
resource "aws_sqs_queue" "orders_dlq" {
  name = "orders-dlq"
}

resource "aws_sqs_queue" "orders" {
  name                      = "orders"
  visibility_timeout_seconds = 30
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount     = 3
  })
}

# DynamoDB table with GSI
resource "aws_dynamodb_table" "users" {
  name         = "Users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "UserId"

  attribute { name = "UserId" type = "S" }
  attribute { name = "Email"  type = "S" }

  global_secondary_index {
    name            = "EmailIndex"
    hash_key        = "Email"
    projection_type = "ALL"
  }
}

# Lambda function
resource "aws_iam_role" "lambda_exec" {
  name = "lambda-exec-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

data "archive_file" "handler" {
  type        = "zip"
  output_path = "${path.module}/handler.zip"
  source {
    filename = "handler.py"
    content  = <<-EOF
      import json
      def handler(event, context):
          return {"statusCode": 200, "body": json.dumps({"ok": True})}
    EOF
  }
}

resource "aws_lambda_function" "api" {
  function_name    = "api-handler"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  filename         = data.archive_file.handler.output_path
  source_code_hash = data.archive_file.handler.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.users.name
      QUEUE_URL  = aws_sqs_queue.orders.url
    }
  }
}

output "s3_bucket"     { value = aws_s3_bucket.app_data.bucket }
output "sqs_queue_url" { value = aws_sqs_queue.orders.url }
output "lambda_arn"    { value = aws_lambda_function.api.arn }
```

---

## 4. Run tfstack

```bash
# Initialise — downloads providers, connects backend to Garage
tfstack init

# Preview changes
tfstack plan

# Apply — creates all resources in KumoStack, writes state to Garage
tfstack apply -auto-approve
```

Expected output from `apply`:

```
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

Outputs:

lambda_arn    = "arn:aws:lambda:us-east-1:000000000000:function:api-handler"
s3_bucket     = "my-app-data"
sqs_queue_url = "http://sqs.us-east-1.localhost.kumostack.org:4566/000000000000/orders"
```

---

## 5. Verify resources were created

```bash
# S3
awslocal s3 ls

# SQS
awslocal sqs list-queues

# Lambda
awslocal lambda list-functions --query 'Functions[*].FunctionName'

# DynamoDB
awslocal dynamodb list-tables
```

---

## 6. Verify state is in Garage

```bash
AWS_ACCESS_KEY_ID=GK9ef5917d6d47e3bc0daae850 \
AWS_SECRET_ACCESS_KEY=f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd \
aws s3 ls s3://terraform-state/ --recursive \
  --endpoint-url http://localhost:3900

# myproject/terraform.tfstate   (your state file)
```

---

## Teardown and re-apply

Because state lives in Garage (not in KumoStack), you can tear down and recreate the entire KumoStack stack without losing state:

```bash
# Stop everything
docker compose down

# Start again — state is still in Garage
docker compose up -d

# Re-apply — Terraform knows what already exists (state says so)
tfstack apply -auto-approve
# Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
```

---

## Multi-workspace — isolate per account

Use Terraform workspaces to give each KumoStack account its own isolated state:

```bash
tfstack workspace new dev-team
tfstack workspace new staging
tfstack workspace new production

tfstack workspace select dev-team
tfstack apply -auto-approve    # state → terraform-state/myproject/env:/dev-team/...

tfstack workspace select production
tfstack apply -auto-approve    # state → terraform-state/myproject/env:/production/...
```

List all workspaces:

```bash
tfstack workspace list
# * dev-team
#   staging
#   production
```

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `KUMOSTACK_HOSTNAME` | `localhost` | KumoStack host |
| `GATEWAY_PORT` | `4566` | KumoStack port |
| `AWS_ENDPOINT_URL` | — | Override all service endpoints at once |
| `TF_CMD` | `terraform` | Path to the `terraform` binary |
| `DRY_RUN` | `0` | Write override file but don't run terraform |

```bash
# Point tfstack at a remote KumoStack instance
KUMOSTACK_HOSTNAME=192.168.1.10 GATEWAY_PORT=4566 tfstack plan
```

---

## Garage vs KumoStack S3 for state

| | KumoStack S3 | Garage |
|---|---|---|
| Default persistence | Ephemeral | Always persists to disk |
| Survives `docker compose down` | Only with `S3_PERSIST=1` | Yes |
| Purpose | Emulate S3 behaviour | Durable object storage |
| Port | `4566` | `3900` |
| Best for | Application S3 testing | Terraform state, log archives |

Use KumoStack S3 (`localhost:4566`) for application resources.  
Use Garage (`localhost:3900`) for Terraform state and log cold archives.

---

## Destroy resources

```bash
tfstack destroy -auto-approve
# Destroy complete! Resources: 8 destroyed.
```

State in Garage is updated to empty — resources are gone from KumoStack, state is preserved.
