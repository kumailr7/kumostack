# Port Reference

All KumoStack services and their host-mapped ports.

| Port | Service | URL | Notes |
|---|---|---|---|
| **4566** | KumoStack (AWS API) | `http://localhost:4566` | All AWS service endpoints |
| **3002** | Grafana | `http://localhost:3002` | admin / admin |
| **3003** | KumoStack Dashboard | `http://localhost:3003` | Main UI |
| **8082** | Stackport | `http://localhost:8082` | AWS resource browser |
| **8083** | draw.io | `http://localhost:8083` | Architecture diagram editor |
| **9091** | Prometheus | `http://localhost:9091` | Metrics scraper |
| **8081** | cAdvisor | `http://localhost:8081` | Container metrics |
| **9121** | redis_exporter | `http://localhost:9121` | Redis Prometheus metrics |
| **6379** | Redis | `localhost:6379` | Used by KumoStack internally |
| **3100** | Loki | `http://localhost:3100` | Log aggregation |
| **8686** | Vector | `http://localhost:8686` | Log pipeline API |
| **3900** | Garage (S3 API) | `http://localhost:3900` | Cold log archive S3 |
| **3903** | Garage (Admin API) | `http://localhost:3903` | Garage cluster management |

---

## AWS service endpoints

All services share the single KumoStack endpoint at port **4566**. The endpoint is the same for every service:

```
http://localhost:4566
```

```bash
# Every awslocal command targets this endpoint automatically
awslocal s3 ls
awslocal lambda list-functions
awslocal sqs list-queues
```

To call the raw HTTP API directly:

```bash
curl -s http://localhost:4566/health | python3 -m json.tool
```

---

## Internal Docker network ports

Inside the Docker network (`kumostack_default`), services use these hostnames:

| Internal hostname | Service |
|---|---|
| `kumostack:4566` | KumoStack AWS API |
| `grafana:3000` | Grafana (internal port 3000) |
| `prometheus:9090` | Prometheus |
| `loki:3100` | Loki |
| `vector:8686` | Vector |
| `garage:3900` | Garage S3 API |
| `redis:6379` | Redis |
| `cadvisor:8080` | cAdvisor |
| `redis-exporter:9121` | redis_exporter |
| `stackport:3000` | Stackport |
| `kumostack-drawio:8080` | draw.io |
