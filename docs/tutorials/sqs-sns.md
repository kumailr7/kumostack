# SQS & SNS — Messaging

Build event-driven workflows with SQS queues and SNS topics, including fan-out patterns and dead-letter queues.

**Time:** ~20 minutes  
**Services:** SQS, SNS, Lambda

---

## SQS — Simple Queue Service

### Create standard and FIFO queues

```bash
# Standard queue
awslocal sqs create-queue --queue-name orders

# FIFO queue (exactly-once, ordered delivery)
awslocal sqs create-queue \
  --queue-name payments.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true
```

### Send and receive messages

```bash
QUEUE_URL=$(awslocal sqs get-queue-url \
  --queue-name orders --query QueueUrl --output text)

# Send a message
awslocal sqs send-message \
  --queue-url $QUEUE_URL \
  --message-body '{"orderId":"ORD-001","total":99.50}' \
  --message-attributes 'Source={DataType=String,StringValue=checkout}'

# Receive and process
awslocal sqs receive-message \
  --queue-url $QUEUE_URL \
  --max-number-of-messages 10 \
  --visibility-timeout 30

# Delete after processing
RECEIPT=$(awslocal sqs receive-message --queue-url $QUEUE_URL \
  --query 'Messages[0].ReceiptHandle' --output text)

awslocal sqs delete-message \
  --queue-url $QUEUE_URL \
  --receipt-handle $RECEIPT
```

### Dead-Letter Queue (DLQ)

```bash
# Create the DLQ
awslocal sqs create-queue --queue-name orders-dlq

DLQ_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url $(awslocal sqs get-queue-url --queue-name orders-dlq --query QueueUrl --output text) \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

# Attach DLQ to main queue (max 3 receive attempts)
awslocal sqs set-queue-attributes \
  --queue-url $QUEUE_URL \
  --attributes "{
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }"
```

---

## SNS — Simple Notification Service

### Create a topic and subscribe

```bash
# Create a topic
TOPIC_ARN=$(awslocal sns create-topic \
  --name order-events --query TopicArn --output text)

# Subscribe an SQS queue to the topic
QUEUE_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

awslocal sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol sqs \
  --notification-endpoint $QUEUE_ARN

# Subscribe an HTTP endpoint
awslocal sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol http \
  --notification-endpoint http://localhost:8083/webhook
```

### Fan-out: one publish → many queues

```bash
# Create two subscriber queues
awslocal sqs create-queue --queue-name inventory-service
awslocal sqs create-queue --queue-name email-service

# Subscribe both to the same topic
for queue in inventory-service email-service; do
  Q_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url $(awslocal sqs get-queue-url --queue-name $queue --query QueueUrl --output text) \
    --attribute-names QueueArn --query Attributes.QueueArn --output text)
  awslocal sns subscribe --topic-arn $TOPIC_ARN --protocol sqs --notification-endpoint $Q_ARN
done

# Publish once — both queues receive the message
awslocal sns publish \
  --topic-arn $TOPIC_ARN \
  --message '{"orderId":"ORD-002","status":"confirmed"}' \
  --subject "OrderConfirmed"
```

### SNS → Lambda

```bash
LAMBDA_ARN=$(awslocal lambda get-function \
  --function-name my-handler --query Configuration.FunctionArn --output text)

awslocal sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol lambda \
  --notification-endpoint $LAMBDA_ARN
```

---

## View in Grafana

- **AWS SQS** dashboard: Messages Visible, Sent, Age of Oldest Message
- **AWS SNS** dashboard: Published, Delivered, Failed counts
