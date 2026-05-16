# Terraform + Garage S3 Backend + KumoStack

Use Garage as a durable S3 remote backend for Terraform state while provisioning resources against KumoStack.

## Why Garage instead of KumoStack S3?

| | KumoStack S3 | Garage |
|---|---|---|
| Persists across restarts | Only with `S3_PERSIST=1` | Always — writes to disk |
| Designed for state locking | No | Yes (via S3 object locking) |
| Survives `docker compose down` | Volume-dependent | Yes |
| Port | 4566 | 3900 |

## Quick start

```bash
# 1. No install needed — use bin/tfstack directly (or add bin/ to PATH)
export PATH="/path/to/kumostack/bin:$PATH"

# 2. (Optional) source Garage credentials from .env so you can drop inline keys
set -a; source ../../.env; set +a
export AWS_ACCESS_KEY_ID=$GARAGE_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$GARAGE_SECRET_KEY

# 3. Init — Terraform downloads providers, backend connects to Garage
tfstack init

# 4. Plan
tfstack plan

# 5. Apply
tfstack apply -auto-approve
```

## What tfstack does

`tfstack` wraps the `terraform` binary. Before running any command it writes a temporary `kumostack_providers_override.tf` that redirects every AWS provider endpoint to `localhost:4566`, then cleans it up afterwards. You write standard Terraform — tfstack handles the endpoint plumbing.

No `pip install` required. `bin/tfstack` auto-detects `.venv`, falls back to `uv sync`, then falls back to injecting `PYTHONPATH`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `KUMOSTACK_HOSTNAME` | `localhost` | KumoStack host |
| `GATEWAY_PORT` | `4566` | KumoStack port |
| `AWS_ENDPOINT_URL` | — | Override all endpoints at once |

## Multi-workspace (multi-account)

Use Terraform workspaces to isolate state per KumoStack account:

```bash
tfstack workspace new dev-team
tfstack workspace new production
tfstack workspace select dev-team
tfstack apply -auto-approve
```

Each workspace stores state at a different key in Garage:
```
terraform-state/
  kumostack/demo/env:/dev-team/terraform.tfstate
  kumostack/demo/env:/production/terraform.tfstate
```

## Inspect state in Garage

```bash
# Load credentials from .env
set -a; source ../../.env; set +a

AWS_ACCESS_KEY_ID=$GARAGE_ACCESS_KEY \
AWS_SECRET_ACCESS_KEY=$GARAGE_SECRET_KEY \
aws s3 ls s3://terraform-state/ --recursive \
  --endpoint-url http://localhost:3900
```
