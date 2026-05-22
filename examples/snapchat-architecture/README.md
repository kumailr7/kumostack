# Snapchat Architecture Demo — KumoStack Edition

Runs a small-scale simulation of Snap's real AWS architecture against a local
KumoStack instance. Every AWS API call is real — only the scale is reduced.

## Architecture

```
iOS/Android ──► EKS Gateway ──► Media Service ──► S3 + CloudFront
                            ──► MCS            ──► DynamoDB (message state)
                            ──► Friend Graph   ──► ElastiCache + DynamoDB
                            ──► Snap DB        ──► DynamoDB (snap metadata)
```

| Service | Role | KumoStack resource |
|---|---|---|
| EKS Gateway | Single entry point, routes to microservices | `eks` cluster |
| Media Service | Stores snap images | Lambda → S3 |
| MCS | Tracks message delivery state | Lambda → DynamoDB |
| Friend Graph | Checks sender/recipient are friends | Lambda → DynamoDB (simulates ElastiCache Redis) |
| Snap DB | Persists snap metadata + CDN URL | Lambda → DynamoDB |
| CloudFront | Serves media from S3 at the edge | CloudFront distribution → S3 |

## Prerequisites

```bash
# KumoStack must be running
docker compose up -d

# Install boto3 (only dependency)
pip install boto3
```

## Usage

```bash
# Run the full demo
python3 simulate.py

# Tear down then re-run (clean slate)
python3 simulate.py --reset

# Tear down only
python3 simulate.py --teardown
```

## What it simulates

1. **Infrastructure setup** — creates S3, 3 DynamoDB tables, ElastiCache, EKS cluster,
   CloudFront distribution, IAM role, and 4 Lambda functions (one per microservice)

2. **Friend graph seeding** — alice, bob, charlie, diana get bidirectional friendships

3. **Snap sends** — 4 sends are attempted:
   - `alice → bob` ✓ (friends, snap delivered)
   - `bob → diana` ✓ (friends, snap delivered)
   - `charlie → diana` ✗ (not friends, Gateway blocks)
   - `alice → eve` ✗ (eve has no friends, Gateway blocks)

4. **Snap receives** — bob and diana open their snaps:
   - Gateway invokes Snap DB to fetch metadata
   - CloudFront serves the media (origin fetch from S3)
   - MCS updates message state to OPENED

5. **Summary** — counts across all tables and S3

## Inspect the data after the run

```bash
# All delivered messages
aws dynamodb scan --table-name snap-mcs-messages \
  --endpoint-url http://localhost:4566

# All snap metadata
aws dynamodb scan --table-name snap-snap-metadata \
  --endpoint-url http://localhost:4566

# Friend graph
aws dynamodb scan --table-name snap-friend-graph \
  --endpoint-url http://localhost:4566

# Media objects in S3
aws s3 ls s3://snap-media-demo/snaps/ \
  --endpoint-url http://localhost:4566

# Lambda function list (4 microservices)
aws lambda list-functions --endpoint-url http://localhost:4566

# EKS cluster
aws eks describe-cluster --name snap-demo-cluster \
  --endpoint-url http://localhost:4566

# ElastiCache cluster
aws elasticache describe-cache-clusters \
  --cache-cluster-id snap-friend-cache \
  --endpoint-url http://localhost:4566
```
