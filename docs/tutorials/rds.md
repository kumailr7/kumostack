# RDS — Managed Databases

Spin up a real PostgreSQL or MySQL database inside KumoStack, connect to it, run migrations, and monitor it in Grafana.

**Time:** ~20 minutes  
**Services:** RDS, Secrets Manager

!!! info "Real Docker"
    KumoStack's RDS emulation spins up an actual Docker container running PostgreSQL or MySQL — not a mock. You get a real database engine.

---

## Prerequisites

Make sure `DOCKER_NETWORK=kumostack_default` is set in your `docker-compose.yml` (already configured in the default KumoStack stack):

```yaml
environment:
  - DOCKER_NETWORK=kumostack_default
```

---

## Create a PostgreSQL instance

```bash
awslocal rds create-db-instance \
  --db-instance-identifier my-postgres \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version "15" \
  --master-username admin \
  --master-user-password secret123 \
  --allocated-storage 20 \
  --db-name appdb \
  --no-multi-az \
  --no-publicly-accessible
```

Wait for the instance to become available (usually ~10 seconds):

```bash
awslocal rds describe-db-instances \
  --db-instance-identifier my-postgres \
  --query 'DBInstances[0].DBInstanceStatus'
# "available"
```

Get the connection endpoint:

```bash
awslocal rds describe-db-instances \
  --db-instance-identifier my-postgres \
  --query 'DBInstances[0].Endpoint'
```

The port is mapped to `localhost:15432` by default.

---

## Connect and run queries

```bash
# Connect with psql
PGPASSWORD=secret123 psql -h localhost -p 15432 -U admin -d appdb

# Or connect directly from the container
docker exec kumostack-rds-my-postgres \
  psql -U admin -d appdb -c "SELECT version();"
```

Create a table and insert data:

```sql
CREATE TABLE users (
  id      SERIAL PRIMARY KEY,
  name    VARCHAR(100) NOT NULL,
  email   VARCHAR(255) UNIQUE NOT NULL,
  created TIMESTAMP DEFAULT NOW()
);

INSERT INTO users (name, email) VALUES
  ('Alice', 'alice@example.com'),
  ('Bob',   'bob@example.com');

SELECT * FROM users;
```

---

## Store the password in Secrets Manager

```bash
awslocal secretsmanager create-secret \
  --name /myapp/db/password \
  --description "RDS master password" \
  --secret-string "secret123"

# Retrieve it in your app
awslocal secretsmanager get-secret-value \
  --secret-id /myapp/db/password \
  --query SecretString --output text
```

---

## MySQL instance

```bash
awslocal rds create-db-instance \
  --db-instance-identifier my-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version "8.0" \
  --master-username root \
  --master-user-password rootpass \
  --allocated-storage 20 \
  --db-name myapp
```

MySQL maps to `localhost:15433` (base port + 1).

---

## Monitor in Grafana

Open `http://localhost:3002` → **AWS Resources** folder → **AWS RDS — my-postgres** dashboard to see:

- CPU Utilization
- DB Connections
- Read / Write IOPS and Latency
- Free Storage Space
- Burst Balance

Push live metrics:

```bash
python3 scripts/realtime_metrics.py --interval 10
```

---

## Clean up

```bash
awslocal rds delete-db-instance \
  --db-instance-identifier my-postgres \
  --skip-final-snapshot
```
