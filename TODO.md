# KumoStack — Observability TODO

## In Progress

### Fix Container Monitoring Dashboard
- [ ] cAdvisor scrape target verified on port 8081
- [ ] Fix Prometheus queries for per-container CPU/memory/network/disk panels
- [ ] Validate all panels return data in Grafana

---

## Planned

### TUI: Auto-add Resources to Grafana
When a user creates an AWS resource via `awslocal` or AWS CLI against KumoStack,
a TUI prompt asks if they want to auto-provision a Grafana dashboard for that resource.

**Implementation plan:**
- [ ] Build `scripts/grafana_add.py` — core helper that calls Grafana HTTP API to
      create/update a dashboard panel for a given resource type + name
- [ ] Build `bin/awslocal-tui` — wrapper around `awslocal` / `aws --endpoint-url`
      that intercepts resource-creating commands (create-queue, create-function,
      create-table, run-instances, etc.) and triggers the TUI prompt after success
- [ ] TUI prompt (using `questionary` + `rich`):
      - Show resource type, name, and available metrics
      - Yes/No prompt: "Add [ResourceType/Name] to Grafana?"
      - On Yes: call Grafana API, print dashboard URL
- [ ] Support resource types:
      - SQS queue → Messages Visible, Sent, Deleted panels
      - Lambda function → Invocations, Errors, Duration panels
      - DynamoDB table → Read/Write Capacity panels
      - EC2 instance → CPUUtilization, NetworkIn/Out panels
      - S3 bucket → NumberOfObjects, BucketSizeBytes panels
      - ElastiCache → CurrConnections, CacheHits, Evictions panels

### Real-time Resource Metrics
- [ ] Reduce Prometheus scrape interval to 5s for cAdvisor and redis-exporter
- [ ] Set Grafana dashboard refresh to 5s for container + redis dashboards
- [ ] Add Grafana Live websocket streaming for CPU/memory panels
- [ ] Create a `scripts/push_realtime_metrics.py` — continuous loop that pushes
      CloudWatch metrics every 10s to simulate live AWS resource activity
      (useful for demo/dev without real traffic)

### CloudWatch Dashboard Enhancements
- [ ] Add per-resource dimension filtering via Grafana template variables
      (e.g. $instance_id, $function_name, $queue_name dropdowns)
- [ ] Add Lambda Duration histogram panel
- [ ] Add SQS Age of Oldest Message panel
- [ ] Add EC2 NetworkIn/NetworkOut panels

### Container Monitoring Enhancements
- [ ] Add per-service memory limit vs usage % gauge
- [ ] Add container restart count alert
- [ ] Add Grafana alert rule: container CPU > 80% for 2 min

---

## Done
- [x] Grafana connected to KumoStack CloudWatch datasource
- [x] Prometheus + redis_exporter added to docker-compose
- [x] cAdvisor added for Docker container monitoring
- [x] CloudWatch dashboard: EC2, Lambda, SQS, DynamoDB, S3 panels
- [x] Redis dashboard: Connected clients, memory, commands/sec, keyspace hits
- [x] Container monitoring dashboard: CPU, memory, network, disk per container
- [x] Fixed CloudWatch `matchExact: true` to use GetMetricData (not SEARCH)
- [x] Sample data pushed for all CloudWatch namespaces
