# Stackport Resource Browser

Stackport is a full CRUD resource browser for every AWS service running in Ministack. Browse, create, update, and delete resources from a clean web UI.

Stackport runs at `http://localhost:8082` and is also embedded as the **Stackport** tab in the Ministack dashboard.

---

## What you can do

- **Browse** all resources across every supported AWS service in a unified table view
- **Create** new resources with validated forms (no CLI required)
- **Delete** resources with a confirmation prompt
- **Inspect** resource details: ARNs, attributes, policies, tags
- **Search** and **filter** across resource names and attributes

---

## Supported services

| Service | Operations |
|---|---|
| S3 | List buckets, create bucket, delete bucket, browse objects |
| Lambda | List functions, view code/config, invoke, delete |
| SQS | List queues, create queue, send/receive/delete messages |
| SNS | List topics, create topic, subscribe, publish, delete |
| DynamoDB | List tables, browse items, put/delete items |
| EC2 | List instances, start/stop/terminate |
| RDS | List clusters and instances, describe parameters |
| ElastiCache | List clusters and nodes |
| Secrets Manager | List secrets, view values, create/delete |
| IAM | List roles, policies, users |
| CloudFormation | List stacks, view resources, events |
| Kinesis | List streams, describe shards |
| Step Functions | List state machines and executions |

---

## Connecting to Ministack

Stackport is pre-configured to point at `http://ministack:4566` (Docker internal network) with credentials `test`/`test` and region `us-east-1`.

If you need to reconfigure:

1. Open `http://localhost:8082`
2. Click the **Settings** (gear) icon in the top-right
3. Update the endpoint URL and credentials

---

## Using Stackport from the dashboard

Click **Stackport** in the sidebar. The resource browser opens full-screen inside the dashboard — the sidebar remains accessible on the left.

To open Stackport in its own browser tab, navigate directly to `http://localhost:8082`.

---

## Example: Create an SQS queue via Stackport

1. Open Stackport → **SQS** in the left service list
2. Click **Create Queue**
3. Fill in the queue name, optionally enable FIFO and content-based deduplication
4. Click **Create** — the queue appears in the table immediately

The queue is available at `http://localhost:4566` just as if you created it with `awslocal sqs create-queue`.
