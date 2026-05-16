# ============================================================
#  KumoStack — Terraform example with Garage S3 remote backend
#
#  Run with:
#    tfstack init
#    tfstack plan
#    tfstack apply -auto-approve
#
#  State is stored durably in Garage (localhost:3900).
#  Resources are provisioned against KumoStack (localhost:4566).
# ============================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Garage as S3 remote backend — persists state across KumoStack restarts
  backend "s3" {
    bucket = "terraform-state"
    key    = "kumostack/demo/terraform.tfstate"
    region = "us-east-1"

    # Terraform AWS provider ≥ 5.x syntax for custom endpoints
    endpoints = {
      s3 = "http://localhost:3900"
    }

    # Credentials from .env.example — source before running tfstack init:
    #   set -a; source ../../.env; set +a
    #   export AWS_ACCESS_KEY_ID=$GARAGE_ACCESS_KEY
    #   export AWS_SECRET_ACCESS_KEY=$GARAGE_SECRET_KEY
    # Or keep inline (these are local-dev-only keys, not real AWS credentials):
    access_key = "GK9ef5917d6d47e3bc0daae850"
    secret_key = "f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd"

    # Required for non-AWS S3-compatible backends
    force_path_style             = true
    skip_credentials_validation  = true
    skip_metadata_api_check      = true
    skip_region_validation       = true
    skip_requesting_account_id   = true
  }
}

# Provider points to KumoStack — tfstack auto-injects this override
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3             = "http://localhost:4566"
    sqs            = "http://localhost:4566"
    lambda         = "http://localhost:4566"
    dynamodb       = "http://localhost:4566"
    iam            = "http://localhost:4566"
    sns            = "http://localhost:4566"
    secretsmanager = "http://localhost:4566"
    cloudwatch     = "http://localhost:4566"
  }
}

# ── S3 ──────────────────────────────────────────────────────
resource "aws_s3_bucket" "app_data" {
  bucket = "my-app-data"
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ── SQS ─────────────────────────────────────────────────────
resource "aws_sqs_queue" "orders" {
  name                      = "orders"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 86400
}

resource "aws_sqs_queue" "orders_dlq" {
  name = "orders-dlq"
}

resource "aws_sqs_queue_redrive_policy" "orders" {
  queue_url = aws_sqs_queue.orders.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount     = 3
  })
}

# ── DynamoDB ─────────────────────────────────────────────────
resource "aws_dynamodb_table" "users" {
  name         = "Users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "UserId"

  attribute {
    name = "UserId"
    type = "S"
  }

  attribute {
    name = "Email"
    type = "S"
  }

  global_secondary_index {
    name            = "EmailIndex"
    hash_key        = "Email"
    projection_type = "ALL"
  }
}

# ── Lambda ───────────────────────────────────────────────────
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
    content  = <<-EOF
      import json
      def handler(event, context):
          return {"statusCode": 200, "body": json.dumps({"message": "hello from kumostack"})}
    EOF
    filename = "handler.py"
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

# ── Outputs ──────────────────────────────────────────────────
output "s3_bucket" {
  value = aws_s3_bucket.app_data.bucket
}

output "sqs_queue_url" {
  value = aws_sqs_queue.orders.url
}

output "dynamodb_table" {
  value = aws_dynamodb_table.users.name
}

output "lambda_arn" {
  value = aws_lambda_function.api.arn
}
