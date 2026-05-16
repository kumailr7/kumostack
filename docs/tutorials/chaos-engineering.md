# Chaos Engineering

Test the resilience of your AWS applications locally before they hit production. KumoStack's built-in Chaos API lets you inject faults at the service level, simulate full region outages, stress Docker containers with Pumba, and inject Lambda execution failures — all without touching real AWS.

**Time:** ~30 minutes  
**Requires:** KumoStack running (`docker compose up -d`)

---

## Overview

KumoStack ships four chaos layers, each targeting a different level of the stack:

| Layer | What it breaks | How |
|---|---|---|
| **Service Faults** | Individual AWS API calls | In-process middleware intercepts SigV4 requests |
| **Region Failover** | All calls to a region | SigV4 credential scope matched → 503 or latency |
| **FIS / Lambda** | Lambda function execution | Injected before the handler runs |
| **Pumba** | Container networking & CPU | Docker socket — runs `gaiaadm/pumba` sidecar |

All state is live in-process and resets when KumoStack restarts.

---

## The Dashboard

Open **[http://localhost:3000](http://localhost:3000)** and click **Chaos** in the left sidebar. Five sub-tabs map to each layer described above. A stats bar at the top shows live counts: active rules, faults fired, Pumba jobs, regions down, and Lambda failures.

---

## 1 · Service Fault Injection

### Create a fault rule

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos \
  -H "Content-Type: application/json" \
  -d '{
    "name":             "SQS throttle test",
    "target_service":   "sqs",
    "target_action":    "SendMessage",
    "fault_type":       "throttle",
    "fault_rate":       0.5,
    "duration_seconds": 60
  }' | jq .
```

| Field | Values | Notes |
|---|---|---|
| `target_service` | `s3`, `sqs`, `lambda`, `dynamodb`, `rds`, `secretsmanager`, `apigateway`, `*` | `*` = all services |
| `target_action` | e.g. `SendMessage`, `GetObject`, `*` | case-insensitive prefix match |
| `target_region` | e.g. `us-east-1`, `*` | omit for all regions |
| `fault_type` | `error`, `throttle`, `timeout`, `unavailable`, `latency` | see below |
| `fault_rate` | `0.0`–`1.0` | probability per request |
| `duration_seconds` | integer, `0` = infinite | auto-expires the rule |

### Fault types

| Type | HTTP status | AWS exception |
|---|---|---|
| `error` | 400 | `InternalFailure` |
| `throttle` | 429 | `ThrottlingException` |
| `timeout` | — | connection closed after `delay_ms` |
| `unavailable` | 503 | `ServiceUnavailableException` |
| `latency` | — | adds `delay_ms` before response |

### List active rules

```bash
curl -s http://localhost:4566/_kumostack/chaos | jq '.rules[] | {name,fault_type,fault_rate,trigger_count}'
```

### Delete a rule

```bash
# delete by ID
curl -s -X DELETE "http://localhost:4566/_kumostack/chaos/<rule-id>"

# delete all
curl -s -X DELETE http://localhost:4566/_kumostack/chaos
```

### Quick preset: DynamoDB slow reads

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos \
  -H "Content-Type: application/json" \
  -d '{
    "name":             "DynamoDB slow reads",
    "target_service":   "dynamodb",
    "target_action":    "GetItem",
    "fault_type":       "latency",
    "fault_rate":       0.8,
    "delay_ms":         2000,
    "duration_seconds": 120
  }'
```

Then call your application and watch `trigger_count` increment:

```bash
watch -n1 'curl -s http://localhost:4566/_kumostack/chaos | jq "[.rules[] | {name,trigger_count}]"'
```

---

## 2 · Region Failover

Simulate a full regional outage. Every API call whose SigV4 credential scope targets the affected region returns `503 ServiceUnavailableException` (DOWN) or receives random 1–3 s extra latency (DEGRADED).

### Take a region down

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/region \
  -H "Content-Type: application/json" \
  -d '{"region": "us-east-1", "status": "down"}'
```

Now test that your application fails over to `eu-central-1`:

```python
import boto3

# This client targets us-east-1 — should now receive 503
ddb_primary = boto3.client(
    "dynamodb",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

# This client targets eu-central-1 — should succeed
ddb_standby = boto3.client(
    "dynamodb",
    endpoint_url="http://localhost:4566",
    region_name="eu-central-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

try:
    ddb_primary.list_tables()
    print("Primary: OK")
except Exception as e:
    print(f"Primary FAILED (expected): {e}")

tables = ddb_standby.list_tables()
print(f"Standby: OK — {tables['TableNames']}")
```

### Degrade a region (latency injection)

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/region \
  -H "Content-Type: application/json" \
  -d '{"region": "us-east-1", "status": "degraded"}'
```

### Restore

```bash
curl -s -X DELETE "http://localhost:4566/_kumostack/chaos/region?id=us-east-1"
```

### Check all region statuses

```bash
curl -s http://localhost:4566/_kumostack/chaos/region | jq .
```

---

## 3 · Lambda FIS — Execution-Level Failures

Inject failures directly inside Lambda function execution — before your handler code runs. Inspired by [failure-lambda](https://github.com/gunnargrosch/failure-lambda) and AWS FIS.

### Inject an exception into all functions

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/lambda-failure \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "*",
    "failure_mode":  "exception",
    "rate":          1.0,
    "exception_msg": "FIS: Simulated Lambda failure"
  }'
```

### Target a specific function at 30 %

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/lambda-failure \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "my-api-handler",
    "failure_mode":  "exception",
    "rate":          0.3,
    "exception_msg": "Transient failure — test retry logic"
  }'
```

### Add artificial latency (simulate cold start / timeout)

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/lambda-failure \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "my-api-handler",
    "failure_mode":  "latency",
    "rate":          0.8,
    "latency_ms":    5000
  }'
```

### Failure modes

| Mode | Effect |
|---|---|
| `exception` | Returns `{"errorMessage": ..., "errorType": "ChaosException"}` |
| `statuscode` | Returns a non-2xx HTTP status (use `status_code` field) |
| `latency` | Sleeps `latency_ms` ms before handing off to the real handler |
| `blacklist` | Blocks invocations whose event matches a key pattern |

### Remove a failure rule

```bash
curl -s -X DELETE "http://localhost:4566/_kumostack/chaos/lambda-failure/my-api-handler"
```

---

## 4 · Pumba — Docker Container Chaos

Pumba injects chaos at the Docker networking and resource layer — packet delay, packet loss, network corruption, CPU stress — directly into running KumoStack containers (RDS, ElastiCache, Redis, etc.).

### Prerequisites

Pumba pulls `gaiaadm/pumba` automatically on first use. The KumoStack Docker socket mount must be present (`/var/run/docker.sock`).

### List available containers

```bash
curl -s http://localhost:4566/_kumostack/chaos/containers | jq '.containers[] | {name, status}'
```

### Add 200 ms network delay to the RDS container

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/pumba \
  -H "Content-Type: application/json" \
  -d '{
    "container":        "kumostack-rds-1",
    "chaos_type":       "network_delay",
    "delay_ms":         200,
    "duration_seconds": 60
  }'
```

### Drop 20 % of packets

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/pumba \
  -H "Content-Type: application/json" \
  -d '{
    "container":        "kumostack-redis-1",
    "chaos_type":       "network_loss",
    "loss_percent":     20,
    "duration_seconds": 30
  }'
```

### Stress 2 CPUs (simulate noisy-neighbour)

```bash
curl -s -X POST http://localhost:4566/_kumostack/chaos/pumba \
  -H "Content-Type: application/json" \
  -d '{
    "container":        "kumostack-rds-1",
    "chaos_type":       "stress_cpu",
    "cpus":             2,
    "duration_seconds": 45
  }'
```

### Pumba chaos types

| `chaos_type` | Effect | Key parameter |
|---|---|---|
| `network_delay` | Add latency to all egress traffic | `delay_ms` |
| `network_loss` | Random packet drop | `loss_percent` |
| `network_corrupt` | Corrupt packets | `loss_percent` (corruption %) |
| `stress_cpu` | Saturate CPU cores | `cpus` |
| `kill` | Send `SIGKILL` to container | — |

### Check running Pumba jobs

```bash
curl -s http://localhost:4566/_kumostack/chaos/pumba-jobs | jq .
```

---

## End-to-end resilience test

Put it all together: simulate a partial outage of your primary region while degrading the RDS network, and verify that your application retries correctly.

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:4566/_kumostack/chaos"

echo "==> 1. Degrade us-east-1 (add latency to all API calls)"
curl -s -X POST "$BASE/region" \
  -H "Content-Type: application/json" \
  -d '{"region":"us-east-1","status":"degraded"}'

echo "==> 2. Throttle 50% of DynamoDB reads"
curl -s -X POST "$BASE" \
  -H "Content-Type: application/json" \
  -d '{"name":"DDB throttle","target_service":"dynamodb","target_action":"GetItem","fault_type":"throttle","fault_rate":0.5,"duration_seconds":120}'

echo "==> 3. Add 100ms packet delay to Redis container"
curl -s -X POST "$BASE/pumba" \
  -H "Content-Type: application/json" \
  -d '{"container":"kumostack-redis-1","chaos_type":"network_delay","delay_ms":100,"duration_seconds":120}'

echo ""
echo "Chaos active. Run your application now and check retry/failover behavior."
echo "Press ENTER to clean up..."
read -r

echo "==> Cleaning up"
curl -s -X DELETE "$BASE"
curl -s -X DELETE "$BASE/region?id=us-east-1"
echo "Done."
```

---

## Route 53 Failover pattern

KumoStack's region chaos is designed to test Route 53 DNS failover. The typical setup:

1. Create Route 53 health checks pointing at your primary region endpoint
2. Create a FAILOVER record set (primary + secondary)
3. Use the Region Failover tab to take the primary region **DOWN**
4. Verify Route 53 returns UNHEALTHY for the primary check and that DNS resolves to the secondary

```bash
# Create a health check for us-east-1
aws --endpoint-url http://localhost:4566 route53 create-health-check \
  --caller-reference "test-$(date +%s)" \
  --health-check-config '{
    "IPAddress":        "127.0.0.1",
    "Port":             4566,
    "Type":             "HTTP",
    "ResourcePath":     "/_kumostack/chaos/region",
    "RequestInterval":  30,
    "FailureThreshold": 3
  }'

# Then take the region down and watch the health check flip
curl -s -X POST http://localhost:4566/_kumostack/chaos/region \
  -H "Content-Type: application/json" \
  -d '{"region":"us-east-1","status":"down"}'
```

---

## Reference — Chaos API

| Method | Path | Description |
|---|---|---|
| `GET` | `/_kumostack/chaos` | List all fault rules |
| `POST` | `/_kumostack/chaos` | Create a fault rule |
| `DELETE` | `/_kumostack/chaos` | Delete all rules |
| `DELETE` | `/_kumostack/chaos/<id>` | Delete one rule |
| `PATCH` | `/_kumostack/chaos/<id>` | Update a rule (`status`, `fault_rate`, etc.) |
| `GET` | `/_kumostack/chaos/region` | Get all region statuses |
| `POST` | `/_kumostack/chaos/region` | Set region status (`healthy`/`degraded`/`down`) |
| `DELETE` | `/_kumostack/chaos/region?id=<region>` | Restore a region |
| `GET` | `/_kumostack/chaos/lambda-failure` | List Lambda failure configs |
| `POST` | `/_kumostack/chaos/lambda-failure` | Create Lambda failure config |
| `DELETE` | `/_kumostack/chaos/lambda-failure/<fn>` | Remove Lambda failure config |
| `POST` | `/_kumostack/chaos/pumba` | Launch a Pumba chaos job |
| `GET` | `/_kumostack/chaos/pumba-jobs` | List running Pumba jobs |
| `GET` | `/_kumostack/chaos/containers` | List targetable containers |

---

## What's next

- **[Lambda tutorial](lambda.md)** — deploy functions to test FIS injection against
- **[RDS tutorial](rds.md)** — run a database and hit it with Pumba network chaos
- **[Terraform & tfstack](terraform.md)** — provision full stacks and chaos-test them end-to-end
