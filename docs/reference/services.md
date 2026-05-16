# Supported AWS Services

Services emulated by KumoStack and their implementation status.

## Compute

| Service | Status | Key operations |
|---|---|---|
| **Lambda** | ✅ Full | Create/invoke/delete functions, layers, event source mappings (SQS, DynamoDB Streams, Kinesis) |
| **EC2** | ✅ Full | Run/start/stop/terminate instances, security groups, key pairs, AMIs |
| **ECS** | ✅ Partial | Task definitions, services, clusters |
| **EKS** | ⚠️ Stub | Cluster describe (no actual Kubernetes) |

## Storage

| Service | Status | Key operations |
|---|---|---|
| **S3** | ✅ Full | Buckets, objects, versioning, lifecycle rules, presigned URLs, events, static hosting |
| **EBS** | ✅ Partial | Volumes, snapshots (attached to EC2) |

## Database

| Service | Status | Key operations |
|---|---|---|
| **RDS** | ✅ Full | PostgreSQL + MySQL instances via real Docker containers, parameter groups, Secrets Manager integration |
| **DynamoDB** | ✅ Full | Tables, GSI/LSI, streams, transactions, batch operations |
| **ElastiCache** | ✅ Full | Redis + Memcached clusters, parameter groups |

## Messaging

| Service | Status | Key operations |
|---|---|---|
| **SQS** | ✅ Full | Standard + FIFO queues, DLQ, visibility timeout, message attributes |
| **SNS** | ✅ Full | Topics, subscriptions (SQS, HTTP, Lambda, email), fan-out |
| **Kinesis** | ✅ Full | Streams, shards, put/get records |
| **EventBridge** | ✅ Partial | Rules, targets (Lambda, SQS) |

## Networking

| Service | Status | Key operations |
|---|---|---|
| **API Gateway** | ✅ Full | REST APIs (v1), HTTP APIs (v2), Lambda proxy, deployments, stages |
| **API Gateway v2** | ✅ Full | HTTP/WebSocket APIs |
| **CloudFront** | ⚠️ Stub | Distribution describe |
| **Route 53** | ✅ Partial | Hosted zones, record sets |

## Security & Identity

| Service | Status | Key operations |
|---|---|---|
| **IAM** | ✅ Full | Roles, policies, users, groups, assume-role |
| **Secrets Manager** | ✅ Full | Create/get/delete secrets, versioning, rotation stubs |
| **KMS** | ✅ Full | Keys, encrypt/decrypt, data key generation |
| **Cognito** | ✅ Partial | User pools, identity pools |
| **STS** | ✅ Full | AssumeRole, GetCallerIdentity |

## Application Integration

| Service | Status | Key operations |
|---|---|---|
| **Step Functions** | ✅ Full | State machines (Express + Standard), executions, activities |
| **SES** | ✅ Partial | Send email (logged, not delivered) |

## Developer Tools

| Service | Status | Key operations |
|---|---|---|
| **CloudFormation** | ✅ Full | Stacks, change sets, stack outputs |
| **CloudWatch** | ✅ Full | Metrics (PutMetricData, GetMetricData), alarms, log groups/streams |
| **CloudWatch Logs** | ✅ Full | Log groups, log streams, put/filter log events |
| **X-Ray** | ✅ Partial | Trace segments (collected, not visualized) |
| **CodeArtifact** | ✅ Partial | Domains, repositories, package publish/get |

## Analytics

| Service | Status | Key operations |
|---|---|---|
| **Glue** | ✅ Partial | Databases, tables, crawlers |
| **Athena** | ✅ Partial | Query execution against S3 |
| **MSK (Kafka)** | ⚠️ Stub | Cluster describe |
| **OpenSearch** | ✅ Partial | Domains, basic CRUD |

---

Legend:

- ✅ **Full** — Production-like behaviour, suitable for integration testing
- ✅ **Partial** — Core operations work; some edge cases or advanced features missing
- ⚠️ **Stub** — Returns valid responses but does not execute real behaviour
