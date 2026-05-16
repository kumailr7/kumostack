# Grafana Monitoring

Connect Grafana to Ministack's CloudWatch emulation, Prometheus, and Loki for a complete local observability stack.

Grafana runs at `http://localhost:3002` — login: `admin` / `admin`.

---

## Datasources included out of the box

| Datasource | Type | Purpose |
|---|---|---|
| `cloudwatch` | CloudWatch | AWS service metrics (EC2, Lambda, SQS, RDS…) |
| `Prometheus` | Prometheus | Container and Redis metrics (cAdvisor, redis_exporter) |
| `Loki` | Loki | Container log streams (via Vector) |

---

## CloudWatch datasource

The CloudWatch datasource points to Ministack's emulated CloudWatch API at `http://ministack:4566`.

!!! important "Key settings"
    - **Auth type:** Keys (`test` / `test`)
    - **Default region:** `us-east-1`
    - **Endpoint:** `http://ministack:4566`
    - **`matchExact: true`** — required for `GetMetricData` (Ministack doesn't support `SEARCH()`)

### Push metrics to CloudWatch

```python
import boto3

cw = boto3.client(
    "cloudwatch",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)

cw.put_metric_data(
    Namespace="MyApp/Orders",
    MetricData=[{
        "MetricName": "OrdersProcessed",
        "Value": 42,
        "Unit": "Count",
        "Dimensions": [{"Name": "Environment", "Value": "local"}],
    }]
)
```

Then query it in Grafana with:

```
Namespace:  MyApp/Orders
MetricName: OrdersProcessed
Stat:       Sum
Dimension:  Environment=local
```

---

## Pre-built dashboards

Navigate to `http://localhost:3002/dashboards` → **AWS Resources** folder:

| Dashboard | Panels |
|---|---|
| AWS EC2 | CPU, Network, Disk, Status Checks |
| AWS Lambda | Invocations, Errors, Duration, Concurrency |
| AWS SQS | Messages Visible, Sent, Age |
| AWS RDS | CPU, Connections, IOPS, Latency |
| AWS DynamoDB | Read/Write Capacity, Throttles |
| + 16 more | ElastiCache, S3, CloudFront, ALB, SNS… |

Other folders:

- **Ministack — CloudWatch Overview** — cross-service overview
- **Ministack — Redis Overview** — Redis stats (via Prometheus)
- **Ministack — Container Monitoring** — Docker container CPU/memory/network
- **Log Archiving — Vector + Loki + S3 + Garage**

---

## Push real-time metrics

The `realtime_metrics.py` script continuously pushes live CloudWatch data:

```bash
python3 scripts/realtime_metrics.py             # every 10 seconds
python3 scripts/realtime_metrics.py --interval 5 # every 5 seconds
```

---

## Add a custom dashboard

```bash
curl -X POST http://admin:admin@localhost:3002/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d '{
    "dashboard": {
      "title": "My App Metrics",
      "panels": [{
        "id": 1,
        "title": "Orders Processed",
        "type": "timeseries",
        "datasource": {"type": "cloudwatch", "uid": "afm6kyhcmo0sga"},
        "targets": [{
          "refId": "A",
          "queryMode": "Metrics",
          "metricQueryType": 0,
          "metricEditorMode": 0,
          "region": "us-east-1",
          "namespace": "MyApp/Orders",
          "metricName": "OrdersProcessed",
          "statistic": "Sum",
          "dimensions": {"Environment": ["local"]},
          "matchExact": true,
          "period": "60"
        }]
      }],
      "schemaVersion": 38
    },
    "overwrite": true,
    "folderId": 0
  }'
```
