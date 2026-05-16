# Getting Started with KumoStack

In this tutorial you will start KumoStack, create an S3 bucket, upload a file, invoke a Lambda function, and send a message to SQS — all locally.

**Time:** ~10 minutes  
**Services:** S3, Lambda, SQS

---

## 1. Start KumoStack

```bash
docker run -d -p 4566:4566 --name kumostack kumostackorg/kumostack
```

Verify it is healthy:

```bash
curl http://localhost:4566/_kumostack/health | python3 -m json.tool | head -10
```

You should see `"s3": "available"`, `"lambda": "available"`, etc.

---

## 2. Create an S3 bucket and upload a file

```bash
# Create a bucket
awslocal s3 mb s3://my-first-bucket

# Upload a file
echo "Hello from KumoStack!" > hello.txt
awslocal s3 cp hello.txt s3://my-first-bucket/hello.txt

# List objects
awslocal s3 ls s3://my-first-bucket
```

Expected output:

```
2024-01-01 00:00:00         22 hello.txt
```

---

## 3. Create and invoke a Lambda function

Create a simple Python handler:

```python title="handler.py"
import json

def handler(event, context):
    name = event.get("name", "World")
    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Hello, {name}!"})
    }
```

Package and deploy it:

```bash
zip function.zip handler.py

awslocal lambda create-function \
  --function-name hello \
  --runtime python3.11 \
  --handler handler.handler \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --zip-file fileb://function.zip
```

Invoke it:

```bash
awslocal lambda invoke \
  --function-name hello \
  --payload '{"name":"KumoStack"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
# {"statusCode": 200, "body": "{\"message\": \"Hello, KumoStack!\"}"}
```

---

## 4. Create an SQS queue and send a message

```bash
# Create queue
awslocal sqs create-queue --queue-name my-queue

# Get queue URL
QUEUE_URL=$(awslocal sqs get-queue-url --queue-name my-queue --query QueueUrl --output text)

# Send a message
awslocal sqs send-message \
  --queue-url $QUEUE_URL \
  --message-body "Hello from KumoStack!"

# Receive the message
awslocal sqs receive-message --queue-url $QUEUE_URL
```

---

## 5. View resources in the dashboard

Open `http://localhost:3003` and click **Resource Browser** (Stackport) to see your S3 bucket, Lambda function, and SQS queue listed in the UI.

---

## Next steps

- [S3 in depth →](s3.md)
- [Lambda with layers and container images →](lambda.md)
- [Connect Grafana to see CloudWatch metrics →](../guides/grafana.md)
