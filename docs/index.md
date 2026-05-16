# KumoStack

**Free, open-source local AWS cloud emulator — the drop-in alternative to LocalStack.**

Run 60+ AWS services on your laptop with a single Docker command. No AWS account required. No cost. No cold starts.

```bash
docker run -p 4566:4566 kumostackorg/kumostack
```

---

## What is KumoStack?

KumoStack emulates the AWS API surface locally so you can:

- Develop and test AWS-dependent code without a real AWS account
- Run integration tests in CI with zero cloud cost
- Learn AWS services safely without incurring charges
- Demo cloud architectures to your team offline

---

## Quick start

=== "Docker"

    ```bash
    docker run -d \
      -p 4566:4566 \
      --name kumostack \
      kumostackorg/kumostack
    ```

=== "Docker Compose"

    ```yaml
    services:
      kumostack:
        image: kumostackorg/kumostack:latest
        ports:
          - "4566:4566"
        environment:
          - GATEWAY_PORT=4566
    ```

=== "awslocal"

    Install the `awslocal` wrapper and use it like the real AWS CLI:

    ```bash
    # Uses localhost:4566 automatically
    awslocal s3 mb s3://my-bucket
    awslocal sqs create-queue --queue-name my-queue
    awslocal lambda list-functions
    ```

---

## Dashboard & Observability

The full KumoStack stack ships with a built-in dashboard, Grafana monitoring, and log archiving:

| Service | URL | Purpose |
|---|---|---|
| KumoStack API | `localhost:4566` | AWS endpoint |
| Dashboard | `localhost:3003` | Resource browser + tutorials |
| Grafana | `localhost:3002` | CloudWatch, Prometheus, Loki dashboards |
| Stackport | `localhost:8082` | Full AWS resource browser (CRUD) |
| draw.io | `localhost:8083` | Architecture diagram editor |
| Loki | `localhost:3100` | Log aggregation (via Vector) |
| Prometheus | `localhost:9091` | Metrics |
| Garage | `localhost:3900` | Cold log archive (S3-compatible) |

---

## Next steps

- **[Getting Started →](tutorials/getting-started.md)** — your first KumoStack deployment
- **[Tutorials →](tutorials/index.md)** — hands-on guides for every major AWS service
- **[Grafana Monitoring →](guides/grafana.md)** — connect CloudWatch metrics to Grafana
- **[Supported Services →](reference/services.md)** — full list of emulated AWS APIs
