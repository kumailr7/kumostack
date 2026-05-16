# Configuration Reference

Environment variables and volume mounts for tuning the Ministack stack.

---

## Ministack (core)

Set in `docker-compose.yml` under the `ministack` service.

| Variable | Default | Description |
|---|---|---|
| `AWS_DEFAULT_REGION` | `us-east-1` | Default region for all services |
| `S3_PERSIST` | `0` | Persist S3 data across restarts (`1` to enable) |
| `LOG_LEVEL` | `INFO` | Ministack log verbosity (`DEBUG`, `INFO`, `WARN`, `ERROR`) |
| `DOCKER_NETWORK` | _(unset)_ | Docker network name for RDS containers (must be set for RDS to work) |
| `LAMBDA_EXECUTOR` | `local` | Lambda execution backend (`local` or `docker`) |
| `PERSISTENCE` | `0` | Persist all service state (`1` to enable) |

### Volumes

| Mount | Purpose |
|---|---|
| `./data:/var/lib/localstack` | Persistent state (when `PERSISTENCE=1`) |
| `./data/s3:/var/lib/localstack/s3` | S3 object store (when `S3_PERSIST=1`) |
| `/var/run/docker.sock:/var/run/docker.sock` | Required for Lambda-in-Docker and RDS containers |

---

## Grafana

| Variable | Default | Description |
|---|---|---|
| `GF_SECURITY_ADMIN_PASSWORD` | `admin` | Admin password |
| `GF_SECURITY_ADMIN_USER` | `admin` | Admin username |
| `GF_AUTH_ANONYMOUS_ENABLED` | `false` | Allow anonymous access |
| `GF_INSTALL_PLUGINS` | _(see compose)_ | Comma-separated plugin IDs to install at startup |

### Volumes

| Mount | Purpose |
|---|---|
| `grafana-data:/var/lib/grafana` | Dashboards, datasources, preferences |
| `./grafana/provisioning:/etc/grafana/provisioning` | Provisioned datasources and dashboards |

---

## Prometheus

Config file: `prometheus/prometheus.yml`

| Setting | Default | Description |
|---|---|---|
| `global.scrape_interval` | `15s` | How often to scrape targets |
| `global.evaluation_interval` | `15s` | How often to evaluate rules |

Add new scrape targets in `prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: my-app
    static_configs:
      - targets: ["host.docker.internal:9100"]
```

---

## Loki

Config file: `loki/loki-config.yaml`

| Setting | Default | Description |
|---|---|---|
| `limits_config.retention_period` | `720h` | Log retention (30 days) |
| `compactor.delete_request_store` | `filesystem` | Required when retention is enabled |
| `server.http_listen_port` | `3100` | HTTP API port |

---

## Vector

Config file: `vector/vector.toml`

| Variable (env) | Description |
|---|---|
| `GARAGE_S3_ENDPOINT` | Garage S3 API URL for cold archive sink |

To add a new sink, append to `vector/vector.toml` and restart:

```bash
docker compose restart vector
```

---

## Garage (cold storage)

Config file: `garage/garage.toml`

| Setting | Default | Description |
|---|---|---|
| `replication_factor` | `1` | Number of data replicas |
| `s3_api.s3_region` | `us-east-1` | Reported S3 region |
| `s3_api.api_bind_addr` | `[::]:3900` | S3 API listen address |
| `admin.api_bind_addr` | `0.0.0.0:3903` | Admin API listen address |

Access key and secret are pre-set in `docker-compose.yml` via `GARAGE_ACCESS_KEY` and `GARAGE_SECRET_KEY`.

---

## Dashboard

| Variable | Default | Description |
|---|---|---|
| `MINISTACK_CONTAINER` | `ministack` | Container name to read logs from |
| `DRAWIO_ENDPOINT` | `http://ministack-drawio:8080` | draw.io service URL (internal) |
| `NEXT_PUBLIC_GRAFANA_URL` | `http://localhost:3002` | Grafana base URL (client-side) |
