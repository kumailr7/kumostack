# awslocal TUI — Auto-add to Grafana

`awslocal` is a drop-in wrapper around the AWS CLI that intercepts resource-creation commands and offers to add them to Grafana automatically.

---

## How it works

When you run a resource-creating command via `awslocal`, the TUI:

1. Runs the actual AWS CLI command against KumoStack (`localhost:4566`)
2. Detects the resource type (SQS, Lambda, DynamoDB, EC2, S3, ElastiCache)
3. Prompts you in the terminal: **"Add this resource to Grafana?"**
4. If you select **Yes**, creates a scoped Grafana dashboard with metrics pre-wired to that resource's dimensions

---

## Supported resource types

| Command | Grafana dashboard created |
|---|---|
| `awslocal sqs create-queue` | SQS queue metrics (Visible, Sent, Age) |
| `awslocal lambda create-function` | Lambda metrics (Invocations, Errors, Duration) |
| `awslocal dynamodb create-table` | DynamoDB metrics (RCU, WCU, Throttles) |
| `awslocal s3 mb` / `s3api create-bucket` | S3 metrics (Requests, Bytes, Errors) |
| `awslocal ec2 run-instances` | EC2 metrics (CPU, Network, Disk) |
| `awslocal elasticache create-cache-cluster` | ElastiCache metrics (CPU, Memory, Connections) |

---

## Usage

Use `awslocal` exactly as you would use `aws`:

```bash
# Create an SQS queue — TUI will appear after creation
awslocal sqs create-queue --queue-name my-orders

# Create a Lambda — prompted to add to Grafana
awslocal lambda create-function \
  --function-name order-processor \
  --runtime python3.11 \
  --handler handler.main \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --zip-file fileb://function.zip
```

The TUI panel appears in your terminal:

```
╭──────────────────────────────────────╮
│  New SQS Queue: my-orders            │
│  Add a Grafana dashboard for this?   │
│                                      │
│  ► Yes                               │
│    No                                │
╰──────────────────────────────────────╯
```

Selecting **Yes** opens a dashboard at `http://localhost:3002` scoped to that resource.

---

## Skip the prompt (CI / scripting)

Pass `--auto-grafana` to add without prompting:

```bash
awslocal sqs create-queue --queue-name ci-queue --auto-grafana
```

Or set the env var to disable TUI entirely:

```bash
export AWSLOCAL_NO_GRAFANA=1
awslocal sqs create-queue --queue-name ci-queue
```

---

## Installation

`bin/awslocal` is already in the repo. Make it available on your `PATH`:

```bash
export PATH="$PATH:/path/to/kumostack/bin"
```

Or create a symlink:

```bash
ln -s /path/to/kumostack/bin/awslocal /usr/local/bin/awslocal
```

Requires Python 3.8+ and the `rich` + `questionary` packages (installed via `pip install -r requirements.txt`).
