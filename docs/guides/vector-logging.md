# Vector.dev Log Archiving

Build a 3-tier log pipeline: live logs in Loki, warm archives in Ministack S3, cold archives in Garage.

**Stack:** Vector → Loki (live, 30d) → Ministack S3 (hot, 30d) → Garage (cold, 365d)

---

## Architecture

```
Docker containers
      │
      ▼
  Vector.dev  ──► Loki (live queries, 30d retention)
      │
      ├──► Ministack S3  (hot archive, 30d lifecycle rule)
      │
      └──► Garage S3     (cold archive, 365d / 730d for RDS)
```

All services start with `docker compose up -d`. Vector auto-discovers every container via the Docker socket.

---

## Vector pipeline

Vector config lives at `vector/vector.toml`. The pipeline has three stages:

### Source — Docker logs

```toml
[sources.docker_logs]
type = "docker_logs"
exclude_containers = ["ministack-vector"]
```

Reads stdout/stderr from every running container except itself.

### Transforms

```toml
[transforms.enrich]
type = "remap"
inputs = ["docker_logs"]
source = '''
  .service     = get_env_var!("HOSTNAME")
  .category    = "aws"
  .environment = "local"
'''

[transforms.parse_level]
type = "remap"
inputs = ["enrich"]
source = '''
  lowered = downcase(string!(.message))
  if contains(lowered, "error") {
    .level = "error"
  } else if contains(lowered, "warn") {
    .level = "warn"
  } else if contains(lowered, "debug") {
    .level = "debug"
  } else {
    .level = "info"
  }
'''

[transforms.aws_enrich]
type = "remap"
inputs = ["parse_level"]
source = '''
  if exists(.message) {
    msg = string!(.message)
    if contains(msg, "Action=") {
      .aws_action = "detected"
    }
    if contains(msg, "SELECT") || contains(msg, "INSERT") || contains(msg, "UPDATE") {
      .is_sql = true
    }
  }
'''
```

### Sinks

**Loki — live queries**

```toml
[sinks.loki_all]
type    = "loki"
inputs  = ["aws_enrich"]
endpoint = "http://loki:3100"
encoding.codec = "json"

[sinks.loki_all.labels]
service     = "{{ service }}"
level       = "{{ level }}"
category    = "{{ category }}"
environment = "{{ environment }}"
container   = "{{ container_name }}"
```

**Ministack S3 — hot archive**

```toml
[sinks.s3_archive]
type   = "aws_s3"
inputs = ["aws_enrich"]
bucket = "ministack-logs"
region = "us-east-1"
endpoint = "http://ministack:4566"

[sinks.s3_archive.auth]
access_key_id     = "test"
secret_access_key = "test"

[sinks.s3_archive.batch]
timeout_secs = 60

[sinks.s3_archive.encoding]
codec = "json"
```

**Garage — cold archive**

```toml
[sinks.garage_cold_archive]
type   = "aws_s3"
inputs = ["aws_enrich"]
bucket = "logs-cold-archive"
region = "us-east-1"
endpoint = "http://garage:3900"

[sinks.garage_cold_archive.auth]
access_key_id     = "GK9ef5917d6d47e3bc0daae850"
secret_access_key = "f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd"

[sinks.garage_cold_archive.batch]
timeout_secs = 300

[sinks.garage_cold_archive.encoding]
codec = "json"
```

---

## Loki retention

`loki/loki-config.yaml` sets 30-day retention:

```yaml
limits_config:
  retention_period: 720h

compactor:
  working_directory: /loki/compactor
  delete_request_store: filesystem   # required when retention is enabled
```

Query logs at `http://localhost:3002` → **Explore** → Loki datasource.

---

## Ministack S3 lifecycle

Set a 30-day expiry so logs auto-delete from the hot tier:

```bash
awslocal s3api put-bucket-lifecycle-configuration \
  --bucket ministack-logs \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "expire-logs-30d",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "Expiration": {"Days": 30}
    }]
  }'
```

---

## Garage cold storage

Garage is a self-hosted S3-compatible object store. It starts automatically with the stack.

```bash
# Check cluster status
docker exec ministack-garage garage status

# List cold-archive objects
awslocal s3 ls s3://logs-cold-archive/ \
  --endpoint-url http://localhost:3900 \
  --recursive | head -20
```

Access key and secret are pre-configured in `docker-compose.yml`.

---

## View logs in Grafana

Open `http://localhost:3002` → **Explore** and query Loki:

```logql
# All logs from the ministack container
{container="ministack"}

# Error logs across all services
{level="error"}

# RDS/PostgreSQL logs
{service=~".*rds.*"}
```

Pre-built dashboards:

- **Log Archiving — Vector + Loki + S3 + Garage** — pipeline health, error rates, archive throughput
- **Ministack — Container Monitoring** → Logs tab (per-container log streams)
