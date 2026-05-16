# DynamoDB — NoSQL Tables

Create tables, put/get/query items, configure secondary indexes, and enable streams.

**Time:** ~15 minutes  
**Services:** DynamoDB

---

## Create a table

```bash
awslocal dynamodb create-table \
  --table-name Users \
  --attribute-definitions \
    AttributeName=UserId,AttributeType=S \
    AttributeName=Email,AttributeType=S \
  --key-schema \
    AttributeName=UserId,KeyType=HASH \
  --global-secondary-indexes '[{
    "IndexName": "EmailIndex",
    "KeySchema": [{"AttributeName":"Email","KeyType":"HASH"}],
    "Projection": {"ProjectionType":"ALL"}
  }]' \
  --billing-mode PAY_PER_REQUEST
```

---

## Put, get, and query items

```bash
# Put an item
awslocal dynamodb put-item \
  --table-name Users \
  --item '{
    "UserId":  {"S": "u001"},
    "Email":   {"S": "alice@example.com"},
    "Name":    {"S": "Alice"},
    "Age":     {"N": "30"},
    "Active":  {"BOOL": true}
  }'

# Get a single item by primary key
awslocal dynamodb get-item \
  --table-name Users \
  --key '{"UserId": {"S": "u001"}}'

# Query the GSI by email
awslocal dynamodb query \
  --table-name Users \
  --index-name EmailIndex \
  --key-condition-expression "Email = :email" \
  --expression-attribute-values '{":email": {"S": "alice@example.com"}}'
```

---

## Scan with a filter

```bash
awslocal dynamodb scan \
  --table-name Users \
  --filter-expression "Age > :age" \
  --expression-attribute-values '{":age": {"N": "25"}}' \
  --projection-expression "UserId, Name, Age"
```

---

## Update and delete items

```bash
# Update a field
awslocal dynamodb update-item \
  --table-name Users \
  --key '{"UserId": {"S": "u001"}}' \
  --update-expression "SET Age = :newage, UpdatedAt = :now" \
  --expression-attribute-values '{
    ":newage": {"N": "31"},
    ":now":    {"S": "2024-01-01T00:00:00Z"}
  }'

# Delete an item
awslocal dynamodb delete-item \
  --table-name Users \
  --key '{"UserId": {"S": "u001"}}'
```

---

## DynamoDB Streams

```bash
# Enable streams on the table
awslocal dynamodb update-table \
  --table-name Users \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES

# List the stream ARN
awslocal dynamodb describe-table \
  --table-name Users \
  --query 'Table.LatestStreamArn'

# Connect a Lambda function to the stream
STREAM_ARN=$(awslocal dynamodb describe-table \
  --table-name Users \
  --query 'Table.LatestStreamArn' --output text)

awslocal lambda create-event-source-mapping \
  --function-name my-stream-processor \
  --event-source-arn "$STREAM_ARN" \
  --starting-position TRIM_HORIZON \
  --batch-size 10
```

---

## Batch operations

```bash
awslocal dynamodb batch-write-item \
  --request-items '{
    "Users": [
      {"PutRequest": {"Item": {"UserId":{"S":"u002"},"Email":{"S":"bob@example.com"},"Name":{"S":"Bob"}}}},
      {"PutRequest": {"Item": {"UserId":{"S":"u003"},"Email":{"S":"charlie@example.com"},"Name":{"S":"Charlie"}}}}
    ]
  }'
```

---

## View in Grafana

Open `http://localhost:3002` → **AWS Resources** → **AWS DynamoDB** to monitor Read/Write Capacity, Throttled Requests, and Latency.
