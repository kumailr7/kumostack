# EKS + RDS + ALB + Secrets Manager Example

A complete local AWS stack using KumoStack:

| Service | Backend | What you get |
|---|---|---|
| **EKS** | Real k3s Docker container | Full `kubectl` access, deploy real pods |
| **RDS PostgreSQL** | Real postgres Docker container | Real psql, `SELECT version()` works |
| **Secrets Manager** | In-memory API | `GetSecretValue` returns exact JSON |
| **ALB** | API-emulated | Real ARNs/DNS, no traffic proxy |

---

## Prerequisites

- [KumoStack](../../README.md) running: `docker compose up -d`
- Terraform ≥ 1.5
- `kubectl` installed
- `psql` (optional, for direct DB access)
- AWS CLI (optional, for secret retrieval test)

---

## Quick Start

```bash
cd examples/eks-rds-alb

# 1. Initialize and deploy
terraform init
terraform apply -auto-approve

# 2. Generate kubeconfig (adds 'kumostack' context)
bash kubeconfig.sh

# 3. Verify EKS cluster
kubectl --context=kumostack get nodes

# 4. Deploy the sample app
kubectl --context=kumostack apply -f k8s/
kubectl --context=kumostack get pods -n myapp -w

# 5. Check the app status
kubectl --context=kumostack logs -n myapp deployment/sample-app
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  KumoStack (localhost:4566)                                 │
│                                                             │
│  ALB (API-emulated)          Secrets Manager               │
│  └─ Listener :80             └─ rds/myapp/credentials      │
│     └─ Target Group             {"user","pass","host","port"}│
│                                                             │
│  EKS Cluster (REAL k3s)      RDS PostgreSQL (REAL Docker)  │
│  └─ k3s :16443               └─ localhost:15432            │
│     └─ sample-app pod           └─ DB: appdb               │
│        └─ reads secret ─────────────────────────────────┘  │
│        └─ connects to RDS ──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**ALB note:** `CreateLoadBalancer` returns a real ARN and DNS name; `DescribeTargetHealth` works — but ALB does **not** proxy HTTP traffic. Access the sample app via the NodePort service directly.

---

## EKS: Real kubectl Access

KumoStack starts a real `rancher/k3s` container when you create an EKS cluster. After `terraform apply`:

```bash
# Generate kubeconfig
bash kubeconfig.sh

# Check nodes (1 real k3s node)
kubectl --context=kumostack get nodes

# Check all resources
kubectl --context=kumostack get all -n myapp
```

The kubeconfig is written to `~/.kube/config` under context `kumostack`. You can also use it directly:

```bash
export KUBECONFIG=~/.kube/config
kubectl config use-context kumostack
kubectl get nodes
```

### Manual kubeconfig (without the script)

```bash
ENDPOINT=$(terraform output -raw eks_endpoint)   # https://localhost:16443
CA_DATA=$(terraform output -raw eks_ca_cert)      # base64 PEM

kubectl config set-cluster kumostack \
  --server="$ENDPOINT" \
  --certificate-authority=<(echo "$CA_DATA" | base64 -d)

kubectl config set-credentials kumostack-admin --token=test

kubectl config set-context kumostack \
  --cluster=kumostack \
  --user=kumostack-admin

kubectl config use-context kumostack
kubectl get nodes
```

---

## RDS: Real PostgreSQL

```bash
# Direct psql connection
psql "$(terraform output -raw rds_endpoint)" -U appuser -d appdb

# Or use the helper command from outputs
$(terraform output -raw psql_cmd)

# Inside psql:
SELECT version();
CREATE TABLE demo (id SERIAL, value TEXT);
INSERT INTO demo VALUES (DEFAULT, 'hello from KumoStack');
SELECT * FROM demo;
```

The RDS instance runs `postgres:17-alpine` in a Docker container. All standard PostgreSQL operations work.

---

## Secrets Manager: Retrieving Credentials

```bash
# Retrieve the full secret JSON
$(terraform output -raw get_secret_cmd)

# Or manually:
aws secretsmanager get-secret-value \
  --secret-id rds/myapp/credentials \
  --endpoint-url http://localhost:4566 \
  --query SecretString \
  --output text | python3 -m json.tool
```

Output:
```json
{
  "dbname": "appdb",
  "engine": "postgres",
  "host": "localhost",
  "password": "S3cr3tPass!",
  "port": 15432,
  "username": "appuser"
}
```

From inside a pod, the endpoint is `http://host.docker.internal:4566` (set via `AWS_ENDPOINT_URL` env var in the deployment).

---

## Sample App

The `k8s/deployment.yaml` runs a Python/Alpine pod that:

1. Reads `rds/myapp/credentials` from Secrets Manager
2. Connects to RDS and runs `SELECT version()`
3. Serves a JSON status page on port 8080

```bash
# Deploy
kubectl --context=kumostack apply -f k8s/

# Watch pod start
kubectl --context=kumostack get pods -n myapp -w

# Check status (find the NodePort first)
NODE_PORT=$(kubectl --context=kumostack get svc sample-app -n myapp \
  -o jsonpath='{.spec.ports[0].nodePort}')
curl http://localhost:$NODE_PORT

# Expected response:
# {
#   "service": "sample-app",
#   "host": "<pod-hostname>",
#   "secret_status": "OK — host=localhost port=15432",
#   "db_status": "OK",
#   "db_version": "PostgreSQL 17.x ..."
# }
```

---

## ALB: API Verification

```bash
# List load balancers
aws elbv2 describe-load-balancers \
  --endpoint-url http://localhost:4566 \
  --query 'LoadBalancers[0].{DNS:DNSName,State:State.Code,ARN:LoadBalancerArn}'

# Check target group
aws elbv2 describe-target-groups \
  --endpoint-url http://localhost:4566

# Check listeners
aws elbv2 describe-listeners \
  --load-balancer-arn "$(terraform output -raw alb_arn 2>/dev/null || echo '<alb-arn>')" \
  --endpoint-url http://localhost:4566
```

---

## Cleanup

```bash
# Undeploy k8s manifests
kubectl --context=kumostack delete -f k8s/

# Destroy Terraform resources (stops k3s + postgres containers)
terraform destroy -auto-approve

# Remove kubeconfig entry
kubectl config delete-context kumostack
kubectl config delete-cluster kumostack
kubectl config delete-user kumostack-admin
```

---

## Variables

| Variable | Default | Description |
|---|---|---|
| `cluster_name` | `kumostack-cluster` | EKS cluster name |
| `db_identifier` | `myapp-postgres` | RDS instance identifier |
| `db_name` | `appdb` | PostgreSQL database name |
| `db_username` | `appuser` | PostgreSQL username |
| `db_password` | `S3cr3tPass!` | PostgreSQL password |
| `secret_name` | `rds/myapp/credentials` | Secrets Manager secret name |

Override via `terraform.tfvars` or `-var` flags:

```bash
terraform apply -var="db_password=mypassword" -var="cluster_name=my-cluster"
```

---

## Outputs

```bash
terraform output                  # all outputs
terraform output rds_endpoint     # host:port for psql
terraform output eks_endpoint     # https://localhost:16443
terraform output secret_arn       # arn:aws:secretsmanager:...
terraform output alb_dns_name     # <name>.elb.amazonaws.com
terraform output architecture     # summary diagram
```
