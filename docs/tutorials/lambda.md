# Lambda — Serverless Functions

Deploy Python, Node.js, and container-based Lambda functions, set up environment variables, layers, and trigger invocations locally.

**Time:** ~20 minutes  
**Services:** Lambda, IAM, S3, SQS

---

## Deploy a Python function

```python title="handler.py"
import json, os, boto3

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)

def handler(event, context):
    bucket = event["bucket"]
    key    = event["key"]
    s3.put_object(Bucket=bucket, Key=key, Body=b"written by lambda")
    return {"status": "ok", "wrote": f"s3://{bucket}/{key}"}
```

```bash
zip function.zip handler.py

awslocal lambda create-function \
  --function-name s3-writer \
  --runtime python3.11 \
  --handler handler.handler \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --zip-file fileb://function.zip \
  --environment 'Variables={AWS_ENDPOINT_URL=http://localhost:4566}'

# Invoke synchronously
awslocal lambda invoke \
  --function-name s3-writer \
  --payload '{"bucket":"my-app-bucket","key":"written.txt"}' \
  --cli-binary-format raw-in-base64-out \
  out.json && cat out.json
```

---

## Environment variables and configuration

```bash
# Update environment variables
awslocal lambda update-function-configuration \
  --function-name s3-writer \
  --environment 'Variables={
    AWS_ENDPOINT_URL=http://localhost:4566,
    LOG_LEVEL=DEBUG,
    STAGE=local
  }'

# Increase memory and timeout
awslocal lambda update-function-configuration \
  --function-name s3-writer \
  --memory-size 512 \
  --timeout 30
```

---

## Lambda triggered by SQS

```bash
# Create trigger queue
awslocal sqs create-queue --queue-name lambda-trigger
QUEUE_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/lambda-trigger \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

# Map SQS → Lambda
awslocal lambda create-event-source-mapping \
  --function-name s3-writer \
  --event-source-arn "$QUEUE_ARN" \
  --batch-size 5

# Send a test message — Lambda fires automatically
awslocal sqs send-message \
  --queue-url http://localhost:4566/000000000000/lambda-trigger \
  --message-body '{"bucket":"my-app-bucket","key":"triggered.txt"}'
```

---

## Lambda with layers (shared dependencies)

```bash
mkdir -p python/lib/python3.11/site-packages
pip install requests -t python/lib/python3.11/site-packages/
zip -r layer.zip python/

# Publish the layer
LAYER_ARN=$(awslocal lambda publish-layer-version \
  --layer-name requests-layer \
  --zip-file fileb://layer.zip \
  --compatible-runtimes python3.11 \
  --query LayerVersionArn --output text)

# Attach the layer to a function
awslocal lambda update-function-configuration \
  --function-name s3-writer \
  --layers "$LAYER_ARN"
```

---

## Container image Lambda (ECR)

```dockerfile title="Dockerfile"
FROM public.ecr.aws/lambda/python:3.11
COPY handler.py ${LAMBDA_TASK_ROOT}
CMD ["handler.handler"]
```

```bash
# Create ECR repo
awslocal ecr create-repository --repository-name my-lambda

# Build and push (uses local Docker)
docker build -t my-lambda:latest .
docker tag my-lambda:latest localhost:4566/000000000000/my-lambda:latest
docker push localhost:4566/000000000000/my-lambda:latest

# Create Lambda from container image
IMAGE_URI=$(awslocal ecr describe-repositories \
  --repository-names my-lambda \
  --query 'repositories[0].repositoryUri' --output text):latest

awslocal lambda create-function \
  --function-name container-lambda \
  --package-type Image \
  --code ImageUri=$IMAGE_URI \
  --role arn:aws:iam::000000000000:role/lambda-role
```

---

## View metrics in Grafana

Open `http://localhost:3002` → **AWS Resources** folder → **AWS Lambda** dashboard to see Invocations, Errors, Duration, and Throttles for all functions.
