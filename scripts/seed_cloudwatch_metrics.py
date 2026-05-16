#!/usr/bin/env python3
"""
Seed CloudWatch metrics for all AWS resources currently in KumoStack.
Run this after creating resources (or after a chaos test) so Grafana dashboards show data.

Usage:
  python3 scripts/seed_cloudwatch_metrics.py          # one-time seed
  python3 scripts/seed_cloudwatch_metrics.py --loop   # seed every 60s continuously
"""
import argparse, datetime, json, math, random, time
import boto3

ENDPOINT = "http://localhost:4566"
REGION   = "us-east-1"

COMMON = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

cw     = boto3.client("cloudwatch", **COMMON)
lam    = boto3.client("lambda",     **COMMON)
ddb    = boto3.client("dynamodb",   **COMMON)
sqs    = boto3.client("sqs",        **COMMON)
sns    = boto3.client("sns",        **COMMON)
rds    = boto3.client("rds",        **COMMON)
s3     = boto3.client("s3",         **COMMON)
ec     = boto3.client("elasticache",**COMMON)


def now() -> datetime.datetime:
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)


def _put(namespace: str, metric_data: list[dict]):
    """Chunked PutMetricData (max 20 metrics per call)."""
    for i in range(0, len(metric_data), 20):
        cw.put_metric_data(Namespace=namespace, MetricData=metric_data[i:i+20])


def _val(base: float, jitter: float = 0.2) -> float:
    return max(0.0, base * (1 + random.uniform(-jitter, jitter)))


# ── Lambda ────────────────────────────────────────────────────────────────────

def seed_lambda():
    fns = lam.list_functions().get("Functions", [])
    if not fns:
        return
    md = []
    ts = now()
    for fn in fns:
        name = fn["FunctionName"]
        invocations  = int(_val(50))
        errors       = int(_val(3))
        throttles    = int(_val(1))
        duration     = _val(250)  # ms
        dim = [{"Name": "FunctionName", "Value": name}]
        md += [
            {"MetricName": "Invocations",      "Dimensions": dim, "Timestamp": ts, "Value": invocations,  "Unit": "Count"},
            {"MetricName": "Errors",           "Dimensions": dim, "Timestamp": ts, "Value": errors,       "Unit": "Count"},
            {"MetricName": "Throttles",        "Dimensions": dim, "Timestamp": ts, "Value": throttles,    "Unit": "Count"},
            {"MetricName": "Duration",         "Dimensions": dim, "Timestamp": ts, "Value": duration,     "Unit": "Milliseconds"},
            {"MetricName": "ConcurrentExecutions", "Dimensions": dim, "Timestamp": ts, "Value": _val(3),  "Unit": "Count"},
        ]
    _put("AWS/Lambda", md)
    print(f"  Lambda: seeded {len(fns)} functions")


# ── DynamoDB ─────────────────────────────────────────────────────────────────

def seed_dynamodb():
    tables = ddb.list_tables().get("TableNames", [])
    if not tables:
        return
    md = []
    ts = now()
    for table in tables:
        dim = [{"Name": "TableName", "Value": table}]
        md += [
            {"MetricName": "ConsumedReadCapacityUnits",   "Dimensions": dim, "Timestamp": ts, "Value": _val(10),  "Unit": "Count"},
            {"MetricName": "ConsumedWriteCapacityUnits",  "Dimensions": dim, "Timestamp": ts, "Value": _val(5),   "Unit": "Count"},
            {"MetricName": "SuccessfulRequestLatency",    "Dimensions": dim, "Timestamp": ts, "Value": _val(5),   "Unit": "Milliseconds"},
            {"MetricName": "SystemErrors",                "Dimensions": dim, "Timestamp": ts, "Value": 0.0,       "Unit": "Count"},
            {"MetricName": "ThrottledRequests",           "Dimensions": dim, "Timestamp": ts, "Value": 0.0,       "Unit": "Count"},
            {"MetricName": "ReturnedItemCount",           "Dimensions": dim, "Timestamp": ts, "Value": _val(20),  "Unit": "Count"},
        ]
    _put("AWS/DynamoDB", md)
    print(f"  DynamoDB: seeded {len(tables)} tables")


# ── SQS ───────────────────────────────────────────────────────────────────────

def seed_sqs():
    urls = sqs.list_queues().get("QueueUrls", [])
    if not urls:
        return
    md = []
    ts = now()
    for url in urls:
        name = url.split("/")[-1]
        dim  = [{"Name": "QueueName", "Value": name}]
        attrs = sqs.get_queue_attributes(
            QueueUrl=url, AttributeNames=["ApproximateNumberOfMessages"]
        ).get("Attributes", {})
        depth = int(attrs.get("ApproximateNumberOfMessages", 0))
        md += [
            {"MetricName": "NumberOfMessagesSent",        "Dimensions": dim, "Timestamp": ts, "Value": _val(15),   "Unit": "Count"},
            {"MetricName": "NumberOfMessagesReceived",    "Dimensions": dim, "Timestamp": ts, "Value": _val(14),   "Unit": "Count"},
            {"MetricName": "NumberOfMessagesDeleted",     "Dimensions": dim, "Timestamp": ts, "Value": _val(12),   "Unit": "Count"},
            {"MetricName": "ApproximateNumberOfMessagesVisible", "Dimensions": dim, "Timestamp": ts, "Value": float(depth), "Unit": "Count"},
            {"MetricName": "SentMessageSize",             "Dimensions": dim, "Timestamp": ts, "Value": _val(512),  "Unit": "Bytes"},
        ]
    _put("AWS/SQS", md)
    print(f"  SQS: seeded {len(urls)} queues")


# ── SNS ───────────────────────────────────────────────────────────────────────

def seed_sns():
    topics = sns.list_topics().get("Topics", [])
    if not topics:
        return
    md = []
    ts = now()
    for t in topics:
        arn  = t["TopicArn"]
        name = arn.split(":")[-1]
        dim  = [{"Name": "TopicName", "Value": name}]
        md += [
            {"MetricName": "NumberOfMessagesPublished",    "Dimensions": dim, "Timestamp": ts, "Value": _val(10),  "Unit": "Count"},
            {"MetricName": "NumberOfNotificationsDelivered","Dimensions": dim,"Timestamp": ts, "Value": _val(10),  "Unit": "Count"},
            {"MetricName": "NumberOfNotificationsFailed",  "Dimensions": dim, "Timestamp": ts, "Value": 0.0,       "Unit": "Count"},
            {"MetricName": "PublishSize",                  "Dimensions": dim, "Timestamp": ts, "Value": _val(256), "Unit": "Bytes"},
        ]
    _put("AWS/SNS", md)
    print(f"  SNS: seeded {len(topics)} topics")


# ── RDS ───────────────────────────────────────────────────────────────────────

def seed_rds():
    instances = rds.describe_db_instances().get("DBInstances", [])
    if not instances:
        return
    md = []
    ts = now()
    for db in instances:
        ident = db["DBInstanceIdentifier"]
        dim   = [{"Name": "DBInstanceIdentifier", "Value": ident}]
        md += [
            {"MetricName": "CPUUtilization",         "Dimensions": dim, "Timestamp": ts, "Value": _val(20),   "Unit": "Percent"},
            {"MetricName": "DatabaseConnections",    "Dimensions": dim, "Timestamp": ts, "Value": _val(5),    "Unit": "Count"},
            {"MetricName": "FreeStorageSpace",       "Dimensions": dim, "Timestamp": ts, "Value": _val(20e9), "Unit": "Bytes"},
            {"MetricName": "ReadLatency",            "Dimensions": dim, "Timestamp": ts, "Value": _val(0.005),"Unit": "Seconds"},
            {"MetricName": "WriteLatency",           "Dimensions": dim, "Timestamp": ts, "Value": _val(0.003),"Unit": "Seconds"},
            {"MetricName": "ReadIOPS",               "Dimensions": dim, "Timestamp": ts, "Value": _val(100),  "Unit": "Count/Second"},
            {"MetricName": "WriteIOPS",              "Dimensions": dim, "Timestamp": ts, "Value": _val(50),   "Unit": "Count/Second"},
        ]
    _put("AWS/RDS", md)
    print(f"  RDS: seeded {len(instances)} instances")


# ── S3 ────────────────────────────────────────────────────────────────────────

def seed_s3():
    buckets = s3.list_buckets().get("Buckets", [])
    if not buckets:
        return
    md = []
    ts = now()
    for b in buckets:
        name = b["Name"]
        for storage_type in ["StandardStorage"]:
            dim = [{"Name": "BucketName", "Value": name},
                   {"Name": "StorageType", "Value": storage_type}]
            md += [
                {"MetricName": "BucketSizeBytes",       "Dimensions": dim, "Timestamp": ts, "Value": _val(1e6),  "Unit": "Bytes"},
                {"MetricName": "NumberOfObjects",       "Dimensions": dim, "Timestamp": ts, "Value": _val(50),   "Unit": "Count"},
            ]
    _put("AWS/S3", md)
    print(f"  S3: seeded {len(buckets)} buckets")


# ── ElastiCache ───────────────────────────────────────────────────────────────

def seed_elasticache():
    try:
        clusters = ec.describe_cache_clusters().get("CacheClusters", [])
    except Exception:
        return
    if not clusters:
        return
    md = []
    ts = now()
    for c in clusters:
        cid = c["CacheClusterId"]
        dim = [{"Name": "CacheClusterId", "Value": cid}]
        md += [
            {"MetricName": "CPUUtilization",    "Dimensions": dim, "Timestamp": ts, "Value": _val(15),   "Unit": "Percent"},
            {"MetricName": "CacheHits",         "Dimensions": dim, "Timestamp": ts, "Value": _val(100),  "Unit": "Count"},
            {"MetricName": "CacheMisses",       "Dimensions": dim, "Timestamp": ts, "Value": _val(10),   "Unit": "Count"},
            {"MetricName": "CurrConnections",   "Dimensions": dim, "Timestamp": ts, "Value": _val(8),    "Unit": "Count"},
            {"MetricName": "NetworkBytesIn",    "Dimensions": dim, "Timestamp": ts, "Value": _val(4096), "Unit": "Bytes"},
            {"MetricName": "NetworkBytesOut",   "Dimensions": dim, "Timestamp": ts, "Value": _val(8192), "Unit": "Bytes"},
        ]
    _put("AWS/ElastiCache", md)
    print(f"  ElastiCache: seeded {len(clusters)} clusters")


# ── Main ─────────────────────────────────────────────────────────────────────

def seed_all():
    print(f"Seeding CloudWatch metrics at {datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC")
    seed_lambda()
    seed_dynamodb()
    seed_sqs()
    seed_sns()
    seed_rds()
    seed_s3()
    seed_elasticache()
    print("Done.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="seed every 60 s indefinitely")
    ap.add_argument("--interval", type=int, default=60, help="seconds between seeding in --loop mode")
    args = ap.parse_args()

    if args.loop:
        print(f"Running metric seeder every {args.interval}s. Ctrl-C to stop.")
        while True:
            seed_all()
            time.sleep(args.interval)
    else:
        seed_all()
