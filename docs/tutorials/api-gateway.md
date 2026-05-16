# API Gateway

Create REST and HTTP APIs backed by Lambda functions with local routing and CORS support.

**Time:** ~25 minutes  
**Services:** API Gateway, Lambda, IAM

---

## Create a REST API backed by Lambda

### 1. Deploy the Lambda backend

```python title="api_handler.py"
import json

def handler(event, context):
    method = event["httpMethod"]
    path   = event["path"]
    body   = json.loads(event.get("body") or "{}")

    if method == "GET" and path == "/items":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"items": ["apple", "banana", "cherry"]})
        }

    if method == "POST" and path == "/items":
        name = body.get("name", "unknown")
        return {
            "statusCode": 201,
            "body": json.dumps({"created": name})
        }

    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
```

```bash
zip api.zip api_handler.py

awslocal lambda create-function \
  --function-name api-backend \
  --runtime python3.11 \
  --handler api_handler.handler \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --zip-file fileb://api.zip
```

### 2. Create the REST API

```bash
# Create the API
API_ID=$(awslocal apigateway create-rest-api \
  --name "Items API" --query id --output text)

# Get the root resource
ROOT_ID=$(awslocal apigateway get-resources \
  --rest-api-id $API_ID --query 'items[0].id' --output text)

# Create /items resource
RESOURCE_ID=$(awslocal apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part items \
  --query id --output text)

# Add GET method
awslocal apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method GET \
  --authorization-type NONE

# Integrate GET with Lambda
LAMBDA_ARN=$(awslocal lambda get-function \
  --function-name api-backend --query Configuration.FunctionArn --output text)

awslocal apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations"

# Add POST method the same way
awslocal apigateway put-method \
  --rest-api-id $API_ID --resource-id $RESOURCE_ID \
  --http-method POST --authorization-type NONE

awslocal apigateway put-integration \
  --rest-api-id $API_ID --resource-id $RESOURCE_ID \
  --http-method POST --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations"
```

### 3. Deploy the API

```bash
awslocal apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name local

echo "API URL: http://localhost:4566/restapis/$API_ID/local/_user_request_"
```

### 4. Test it

```bash
BASE="http://localhost:4566/restapis/$API_ID/local/_user_request_"

# GET /items
curl "$BASE/items"
# {"items": ["apple", "banana", "cherry"]}

# POST /items
curl -X POST "$BASE/items" \
  -H "Content-Type: application/json" \
  -d '{"name":"mango"}'
# {"created": "mango"}
```

---

## HTTP API (v2 — simpler, faster)

```bash
# Create HTTP API with Lambda integration in one command
awslocal apigatewayv2 create-api \
  --name "Items HTTP API" \
  --protocol-type HTTP \
  --target "$LAMBDA_ARN"

# List APIs and get the endpoint
awslocal apigatewayv2 get-apis \
  --query 'Items[*].[ApiId,ApiEndpoint]' --output table
```

---

## Monitor in Grafana

Open `http://localhost:3002` → **AWS Resources** → **AWS API Gateway** to see Count, Latency, 4xx/5xx rates, and Cache metrics.
</content>