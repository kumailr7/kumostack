# Garage — Durable Local S3

Garage is a self-hosted S3-compatible object store bundled with KumoStack. It writes data durably to disk, making it the right backend for anything that needs to survive a KumoStack restart: Terraform state, log cold archives, large file storage.

Garage runs at `http://localhost:3900`.

---

## Why Garage alongside KumoStack S3?

| | KumoStack S3 `:4566` | Garage `:3900` |
|---|---|---|
| Purpose | Emulate AWS S3 API behaviour | Durable local object store |
| Persistence | Ephemeral (opt-in with `S3_PERSIST=1`) | Always — writes to disk |
| Survives restart | Volume-dependent | Yes |
| AWS-compatible | Yes | Yes (S3 API) |
| Best for | App S3 testing | Terraform state, log archives, backups |

---

## Credentials

Pre-configured in `.env` (copy from `.env.example`):

```bash
GARAGE_ACCESS_KEY=GK9ef5917d6d47e3bc0daae850
GARAGE_SECRET_KEY=f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd
```

Use these credentials anywhere you need to access Garage — AWS CLI, Terraform backend, boto3, etc.

---

## Cluster status

```bash
docker exec kumostack-garage /garage status
```

```
==== HEALTHY NODES ====
ID                Hostname   Zone  Capacity  DataAvail
76c607a9111482e7  garage     dc1   9.3 GiB   737 GiB (79%)
```

---

## Managing buckets

```bash
# List buckets
docker exec kumostack-garage /garage bucket list

# Create a bucket
docker exec kumostack-garage /garage bucket create my-bucket

# Grant the pre-configured key access
docker exec kumostack-garage /garage bucket allow \
  --read --write --owner my-bucket \
  --key GK9ef5917d6d47e3bc0daae850

# Delete a bucket
docker exec kumostack-garage /garage bucket delete my-bucket
```

---

## Access via AWS CLI

Use the standard AWS CLI with a custom endpoint. Load credentials from `.env`:

```bash
set -a; source .env; set +a

AWS_ACCESS_KEY_ID=$GARAGE_ACCESS_KEY \
AWS_SECRET_ACCESS_KEY=$GARAGE_SECRET_KEY \
aws s3 ls \
  --endpoint-url http://localhost:3900 \
  --region us-east-1
```

Or configure a named profile in `~/.aws/config`:

```ini
[profile garage]
region = us-east-1
endpoint_url = http://localhost:3900
```

```ini title="~/.aws/credentials"
[garage]
aws_access_key_id     = GK9ef5917d6d47e3bc0daae850
aws_secret_access_key = f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd
```

```bash
aws s3 ls --profile garage
aws s3 cp myfile.txt s3://my-bucket/ --profile garage
```

---

## Access via boto3 (Python)

```python
import boto3

garage = boto3.client(
    "s3",
    endpoint_url="http://localhost:3900",
    aws_access_key_id="GK9ef5917d6d47e3bc0daae850",
    aws_secret_access_key="f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd",
    region_name="us-east-1",
)

# Upload
garage.put_object(Bucket="my-bucket", Key="hello.txt", Body=b"hello from garage")

# Download
obj = garage.get_object(Bucket="my-bucket", Key="hello.txt")
print(obj["Body"].read())   # b'hello from garage'

# List
for o in garage.list_objects_v2(Bucket="my-bucket")["Contents"]:
    print(o["Key"], o["Size"])
```

---

## Pre-created buckets

The following buckets are created automatically when the stack starts:

| Bucket | Purpose |
|---|---|
| `logs-cold-archive` | Vector cold log archive (365-day retention) |
| `logs-rds-archive` | Vector RDS/PostgreSQL error log archive |
| `terraform-state` | Terraform remote state (see [Terraform guide](../tutorials/terraform.md)) |

---

## Terraform remote state

See the full guide: [Terraform & tfstack →](../tutorials/terraform.md)

Quick backend config:

```hcl
backend "s3" {
  bucket = "terraform-state"
  key    = "myproject/terraform.tfstate"
  region = "us-east-1"

  endpoints = { s3 = "http://localhost:3900" }

  access_key = "GK9ef5917d6d47e3bc0daae850"
  secret_key = "f536a78459fc476ea0a2defb7b02bb9cfdf7cd806cfcff8e9f1780cacc5dbffd"

  force_path_style            = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  skip_requesting_account_id  = true
}
```

---

## Log archiving

Garage is the cold tier in the 3-tier log pipeline:

```
Vector → Loki (live, 30d) → KumoStack S3 (hot, 30d) → Garage (cold, 365d)
```

See [Vector.dev Log Archiving →](vector-logging.md) for the full pipeline.

---

## Persistence

Garage data is stored in the `garage-data` Docker volume. It survives container restarts and `docker compose down` as long as the volume is not deleted:

```bash
# Data is in the volume — safe across restarts
docker volume ls | grep garage

# Only deleted if you explicitly remove volumes
docker compose down -v    # ← this would delete Garage data, don't do this in production
```
