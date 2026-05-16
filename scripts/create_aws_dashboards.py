#!/usr/bin/env python3
"""
create_aws_dashboards.py
Creates a Grafana folder "AWS Resources" and one dashboard per AWS service
supported by Ministack.  Dashboards follow the monitoringartist reference style:
  https://github.com/monitoringartist/grafana-aws-cloudwatch-dashboards
"""

import json, os, urllib.request, urllib.error, base64, sys
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

GRAFANA_URL  = os.environ.get("GRAFANA_URL",  "http://localhost:3002")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASS = os.environ.get("GRAFANA_PASS", "admin")
CW_UID       = os.environ.get("GRAFANA_CW_UID", "afm6kyhcmo0sga")
REGION       = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

console = Console()

# ─── Grafana helpers ──────────────────────────────────────────────────────────

def _auth():
    return "Basic " + base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()

def _req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        f"{GRAFANA_URL}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "Authorization": _auth()})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def get_or_create_folder(name):
    folders = _req("GET", "/api/folders")
    for f in folders:
        if f["title"] == name:
            return f["uid"]
    r = _req("POST", "/api/folders", {"title": name})
    return r["uid"]

def push_dashboard(dashboard, folder_uid):
    return _req("POST", "/api/dashboards/db",
                {"dashboard": dashboard, "overwrite": True, "folderUid": folder_uid})

# ─── Panel builders ───────────────────────────────────────────────────────────

_pid = 1

def _next_id():
    global _pid
    i = _pid; _pid += 1; return i

def ts_panel(title, targets, x, y, w=12, h=8, unit="short", stack=False):
    return {
        "id": _next_id(), "title": title, "type": "timeseries",
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": {"type": "cloudwatch", "uid": CW_UID},
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {
                    "lineWidth": 1,
                    "fillOpacity": 10,
                    "stacking": {"mode": "normal" if stack else "none"},
                },
            }
        },
        "options": {"legend": {"displayMode": "table", "placement": "bottom",
                               "calcs": ["mean", "max", "last"]}},
    }

def stat_panel(title, targets, x, y, w=6, h=4, unit="short"):
    return {
        "id": _next_id(), "title": title, "type": "stat",
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": {"type": "cloudwatch", "uid": CW_UID},
        "targets": targets,
        "options": {"reduceOptions": {"calcs": ["lastNotNull"]},
                    "colorMode": "background"},
        "fieldConfig": {"defaults": {"unit": unit,
                                      "thresholds": {"steps": [{"color": "green", "value": None}]}}},
    }

def cw(refId, namespace, metric, stat, dim_k="", dim_v="", period="60", label=None):
    dims = {dim_k: [dim_v]} if dim_k else {}
    t = {
        "refId": refId,
        "queryMode": "Metrics", "metricQueryType": 0, "metricEditorMode": 0,
        "region": REGION, "namespace": namespace, "metricName": metric,
        "statistic": stat, "dimensions": dims,
        "matchExact": bool(dims), "period": period,
    }
    if label:
        t["alias"] = label
    return t

# ─── Dashboard definitions ────────────────────────────────────────────────────

def dash(title, service_tag, panels):
    global _pid; _pid = 1
    return {
        "title": title,
        "tags": ["ministack", "aws", service_tag],
        "timezone": "browser", "refresh": "30s", "schemaVersion": 38,
        "panels": panels,
    }


def aws_ec2():
    return dash("AWS EC2", "ec2", [
        ts_panel("CPU Utilization", [
            cw("A","AWS/EC2","CPUUtilization","Average",label="Average"),
            cw("B","AWS/EC2","CPUUtilization","Maximum",label="Max"),
        ], 0, 0, 12, 8, "percent"),
        ts_panel("Network In / Out", [
            cw("A","AWS/EC2","NetworkIn","Average",label="In"),
            cw("B","AWS/EC2","NetworkOut","Average",label="Out"),
        ], 12, 0, 12, 8, "bytes"),
        ts_panel("Disk Read / Write Ops", [
            cw("A","AWS/EC2","DiskReadOps","Average",label="Read"),
            cw("B","AWS/EC2","DiskWriteOps","Average",label="Write"),
        ], 0, 8, 12, 8),
        ts_panel("Disk Read / Write Bytes", [
            cw("A","AWS/EC2","DiskReadBytes","Average",label="Read"),
            cw("B","AWS/EC2","DiskWriteBytes","Average",label="Write"),
        ], 12, 8, 12, 8, "bytes"),
        ts_panel("Network Packets In / Out", [
            cw("A","AWS/EC2","NetworkPacketsIn","Average",label="In"),
            cw("B","AWS/EC2","NetworkPacketsOut","Average",label="Out"),
        ], 0, 16, 12, 8),
        ts_panel("Status Check Failed", [
            cw("A","AWS/EC2","StatusCheckFailed","Sum",label="Total"),
            cw("B","AWS/EC2","StatusCheckFailed_Instance","Sum",label="Instance"),
            cw("C","AWS/EC2","StatusCheckFailed_System","Sum",label="System"),
        ], 12, 16, 12, 8),
        ts_panel("CPU Credit Usage / Balance", [
            cw("A","AWS/EC2","CPUCreditUsage","Average",label="Usage"),
            cw("B","AWS/EC2","CPUCreditBalance","Average",label="Balance"),
        ], 0, 24, 12, 8),
        ts_panel("EBS Volume Read / Write Ops", [
            cw("A","AWS/EBS","VolumeReadOps","Average",label="Read"),
            cw("B","AWS/EBS","VolumeWriteOps","Average",label="Write"),
        ], 12, 24, 12, 8),
    ])


def aws_lambda():
    return dash("AWS Lambda", "lambda", [
        ts_panel("Invocations", [cw("A","AWS/Lambda","Invocations","Sum")], 0, 0, 8, 8),
        ts_panel("Errors", [cw("A","AWS/Lambda","Errors","Sum")], 8, 0, 8, 8),
        ts_panel("Throttles", [cw("A","AWS/Lambda","Throttles","Sum")], 16, 0, 8, 8),
        ts_panel("Duration (avg / max)", [
            cw("A","AWS/Lambda","Duration","Average",label="avg"),
            cw("B","AWS/Lambda","Duration","Maximum",label="max"),
        ], 0, 8, 12, 8, "ms"),
        ts_panel("Concurrent Executions", [
            cw("A","AWS/Lambda","ConcurrentExecutions","Average",label="Concurrent"),
            cw("B","AWS/Lambda","UnreservedConcurrentExecutions","Average",label="Unreserved"),
        ], 12, 8, 12, 8),
        ts_panel("DeadLetterErrors / DestinationDeliveryFailures", [
            cw("A","AWS/Lambda","DeadLetterErrors","Sum",label="DLQ Errors"),
            cw("B","AWS/Lambda","DestinationDeliveryFailures","Sum",label="Dest Failures"),
        ], 0, 16, 12, 8),
        ts_panel("Init Duration", [
            cw("A","AWS/Lambda","InitDuration","Average",label="avg"),
        ], 12, 16, 12, 8, "ms"),
    ])


def aws_sqs():
    return dash("AWS SQS", "sqs", [
        ts_panel("Messages Sent / Received / Deleted", [
            cw("A","AWS/SQS","NumberOfMessagesSent","Sum",label="Sent"),
            cw("B","AWS/SQS","NumberOfMessagesReceived","Sum",label="Received"),
            cw("C","AWS/SQS","NumberOfMessagesDeleted","Sum",label="Deleted"),
        ], 0, 0, 12, 8),
        ts_panel("Approximate Number of Messages", [
            cw("A","AWS/SQS","ApproximateNumberOfMessagesVisible","Average",label="Visible"),
            cw("B","AWS/SQS","ApproximateNumberOfMessagesNotVisible","Average",label="In-flight"),
            cw("C","AWS/SQS","ApproximateNumberOfMessagesDelayed","Average",label="Delayed"),
        ], 12, 0, 12, 8),
        ts_panel("Age of Oldest Message", [
            cw("A","AWS/SQS","ApproximateAgeOfOldestMessage","Maximum",label="Age (s)"),
        ], 0, 8, 12, 8, "s"),
        ts_panel("Sent Message Size", [
            cw("A","AWS/SQS","SentMessageSize","Average",label="avg"),
            cw("B","AWS/SQS","SentMessageSize","Maximum",label="max"),
        ], 12, 8, 12, 8, "bytes"),
        ts_panel("Empty Receives", [
            cw("A","AWS/SQS","NumberOfEmptyReceives","Sum"),
        ], 0, 16, 12, 8),
    ])


def aws_dynamodb():
    return dash("AWS DynamoDB", "dynamodb", [
        ts_panel("Consumed Read / Write Capacity", [
            cw("A","AWS/DynamoDB","ConsumedReadCapacityUnits","Sum",label="Read"),
            cw("B","AWS/DynamoDB","ConsumedWriteCapacityUnits","Sum",label="Write"),
        ], 0, 0, 12, 8),
        ts_panel("Provisioned Read / Write Capacity", [
            cw("A","AWS/DynamoDB","ProvisionedReadCapacityUnits","Average",label="Read"),
            cw("B","AWS/DynamoDB","ProvisionedWriteCapacityUnits","Average",label="Write"),
        ], 12, 0, 12, 8),
        ts_panel("Throttled Requests", [
            cw("A","AWS/DynamoDB","ReadThrottleEvents","Sum",label="Read"),
            cw("B","AWS/DynamoDB","WriteThrottleEvents","Sum",label="Write"),
            cw("C","AWS/DynamoDB","ThrottledRequests","Sum",label="Total"),
        ], 0, 8, 12, 8),
        ts_panel("Successful Request Latency", [
            cw("A","AWS/DynamoDB","SuccessfulRequestLatency","Average",label="avg"),
            cw("B","AWS/DynamoDB","SuccessfulRequestLatency","Maximum",label="max"),
        ], 12, 8, 12, 8, "ms"),
        ts_panel("System / User Errors", [
            cw("A","AWS/DynamoDB","SystemErrors","Sum",label="System"),
            cw("B","AWS/DynamoDB","UserErrors","Sum",label="User"),
        ], 0, 16, 12, 8),
        ts_panel("Returned Item Count", [
            cw("A","AWS/DynamoDB","ReturnedItemCount","Sum"),
        ], 12, 16, 12, 8),
        ts_panel("Conditional Check Failed / Transaction Conflict", [
            cw("A","AWS/DynamoDB","ConditionalCheckFailedRequests","Sum",label="CondCheck"),
            cw("B","AWS/DynamoDB","TransactionConflict","Sum",label="TxConflict"),
        ], 0, 24, 12, 8),
        ts_panel("TimeToLive Deleted Items", [
            cw("A","AWS/DynamoDB","TimeToLiveDeletedItemCount","Sum"),
        ], 12, 24, 12, 8),
    ])


def aws_s3():
    return dash("AWS S3", "s3", [
        ts_panel("Number of Objects", [
            cw("A","AWS/S3","NumberOfObjects","Average",period="86400"),
        ], 0, 0, 12, 8),
        ts_panel("Bucket Size (bytes)", [
            cw("A","AWS/S3","BucketSizeBytes","Average",period="86400"),
        ], 12, 0, 12, 8, "bytes"),
        ts_panel("All Requests", [
            cw("A","AWS/S3","AllRequests","Sum"),
        ], 0, 8, 8, 8),
        ts_panel("Get / Put / Delete Requests", [
            cw("A","AWS/S3","GetRequests","Sum",label="Get"),
            cw("B","AWS/S3","PutRequests","Sum",label="Put"),
            cw("C","AWS/S3","DeleteRequests","Sum",label="Delete"),
        ], 8, 8, 16, 8),
        ts_panel("4xx / 5xx Errors", [
            cw("A","AWS/S3","4xxErrors","Sum",label="4xx"),
            cw("B","AWS/S3","5xxErrors","Sum",label="5xx"),
        ], 0, 16, 12, 8),
        ts_panel("First Byte Latency / Total Request Latency", [
            cw("A","AWS/S3","FirstByteLatency","Average",label="First Byte"),
            cw("B","AWS/S3","TotalRequestLatency","Average",label="Total"),
        ], 12, 16, 12, 8, "ms"),
    ])


def aws_rds():
    return dash("AWS RDS", "rds", [
        ts_panel("CPU Utilization", [
            cw("A","AWS/RDS","CPUUtilization","Average"),
        ], 0, 0, 8, 8, "percent"),
        ts_panel("DB Connections", [
            cw("A","AWS/RDS","DatabaseConnections","Average"),
        ], 8, 0, 8, 8),
        ts_panel("Freeable Memory", [
            cw("A","AWS/RDS","FreeableMemory","Average"),
        ], 16, 0, 8, 8, "bytes"),
        ts_panel("Read / Write IOPS", [
            cw("A","AWS/RDS","ReadIOPS","Average",label="Read"),
            cw("B","AWS/RDS","WriteIOPS","Average",label="Write"),
        ], 0, 8, 12, 8),
        ts_panel("Read / Write Latency", [
            cw("A","AWS/RDS","ReadLatency","Average",label="Read"),
            cw("B","AWS/RDS","WriteLatency","Average",label="Write"),
        ], 12, 8, 12, 8, "s"),
        ts_panel("Read / Write Throughput", [
            cw("A","AWS/RDS","ReadThroughput","Average",label="Read"),
            cw("B","AWS/RDS","WriteThroughput","Average",label="Write"),
        ], 0, 16, 12, 8, "bytes"),
        ts_panel("Free Storage Space", [
            cw("A","AWS/RDS","FreeStorageSpace","Average"),
        ], 12, 16, 12, 8, "bytes"),
        ts_panel("Queue Depth / Disk Queue Depth", [
            cw("A","AWS/RDS","DiskQueueDepth","Average"),
        ], 0, 24, 12, 8),
        ts_panel("Swap Usage / Burst Balance", [
            cw("A","AWS/RDS","SwapUsage","Average",label="Swap"),
            cw("B","AWS/RDS","BurstBalance","Average",label="Burst"),
        ], 12, 24, 12, 8, "bytes"),
    ])


def aws_elasticache():
    return dash("AWS ElastiCache", "elasticache", [
        ts_panel("CPU Utilization", [
            cw("A","AWS/ElastiCache","CPUUtilization","Average"),
        ], 0, 0, 8, 8, "percent"),
        ts_panel("Cache Hits / Misses", [
            cw("A","AWS/ElastiCache","CacheHits","Sum",label="Hits"),
            cw("B","AWS/ElastiCache","CacheMisses","Sum",label="Misses"),
        ], 8, 0, 8, 8),
        ts_panel("Curr Connections", [
            cw("A","AWS/ElastiCache","CurrConnections","Average"),
        ], 16, 0, 8, 8),
        ts_panel("Evictions / Reclaimed", [
            cw("A","AWS/ElastiCache","Evictions","Sum",label="Evictions"),
            cw("B","AWS/ElastiCache","Reclaimed","Sum",label="Reclaimed"),
        ], 0, 8, 12, 8),
        ts_panel("Bytes Used for Cache / Freeable Memory", [
            cw("A","AWS/ElastiCache","BytesUsedForCache","Average",label="Used"),
            cw("B","AWS/ElastiCache","FreeableMemory","Average",label="Free"),
        ], 12, 8, 12, 8, "bytes"),
        ts_panel("Network Bytes In / Out", [
            cw("A","AWS/ElastiCache","NetworkBytesIn","Average",label="In"),
            cw("B","AWS/ElastiCache","NetworkBytesOut","Average",label="Out"),
        ], 0, 16, 12, 8, "bytes"),
        ts_panel("Get / Set Commands", [
            cw("A","AWS/ElastiCache","GetTypeCmds","Sum",label="Get"),
            cw("B","AWS/ElastiCache","SetTypeCmds","Sum",label="Set"),
        ], 12, 16, 12, 8),
        ts_panel("Curr Items / New Connections", [
            cw("A","AWS/ElastiCache","CurrItems","Average",label="Items"),
            cw("B","AWS/ElastiCache","NewConnections","Sum",label="New Conn"),
        ], 0, 24, 12, 8),
    ])


def aws_ecs():
    return dash("AWS ECS", "ecs", [
        ts_panel("CPU Utilization", [
            cw("A","AWS/ECS","CPUUtilization","Average"),
        ], 0, 0, 12, 8, "percent"),
        ts_panel("Memory Utilization", [
            cw("A","AWS/ECS","MemoryUtilization","Average"),
        ], 12, 0, 12, 8, "percent"),
        ts_panel("CPU Reserved / Used", [
            cw("A","AWS/ECS","CPUReservation","Average",label="Reserved"),
            cw("B","AWS/ECS","CPUUtilization","Average",label="Used"),
        ], 0, 8, 12, 8, "percent"),
        ts_panel("Memory Reserved / Used", [
            cw("A","AWS/ECS","MemoryReservation","Average",label="Reserved"),
            cw("B","AWS/ECS","MemoryUtilization","Average",label="Used"),
        ], 12, 8, 12, 8, "percent"),
    ])


def aws_apigateway():
    return dash("AWS API Gateway", "apigateway", [
        ts_panel("Count (Requests)", [
            cw("A","AWS/ApiGateway","Count","Sum"),
        ], 0, 0, 8, 8),
        ts_panel("Latency (avg / p99)", [
            cw("A","AWS/ApiGateway","Latency","Average",label="avg"),
            cw("B","AWS/ApiGateway","IntegrationLatency","Average",label="integration avg"),
        ], 8, 0, 8, 8, "ms"),
        ts_panel("4xx / 5xx Errors", [
            cw("A","AWS/ApiGateway","4XXError","Sum",label="4xx"),
            cw("B","AWS/ApiGateway","5XXError","Sum",label="5xx"),
        ], 16, 0, 8, 8),
        ts_panel("Cache Hit / Miss Count", [
            cw("A","AWS/ApiGateway","CacheHitCount","Sum",label="Hit"),
            cw("B","AWS/ApiGateway","CacheMissCount","Sum",label="Miss"),
        ], 0, 8, 12, 8),
        ts_panel("Data Processed", [
            cw("A","AWS/ApiGateway","DataProcessed","Sum"),
        ], 12, 8, 12, 8, "bytes"),
    ])


def aws_sns():
    return dash("AWS SNS", "sns", [
        ts_panel("Published / Delivered Messages", [
            cw("A","AWS/SNS","NumberOfMessagesPublished","Sum",label="Published"),
            cw("B","AWS/SNS","NumberOfNotificationsDelivered","Sum",label="Delivered"),
        ], 0, 0, 12, 8),
        ts_panel("Failed / Filtered Notifications", [
            cw("A","AWS/SNS","NumberOfNotificationsFailed","Sum",label="Failed"),
            cw("B","AWS/SNS","NumberOfNotificationsFilteredOut","Sum",label="Filtered"),
        ], 12, 0, 12, 8),
        ts_panel("Published Size / Bytes Delivered", [
            cw("A","AWS/SNS","PublishSize","Average",label="Published"),
            cw("B","AWS/SNS","NumberOfNotificationsDelivered","Sum",label="Delivered count"),
        ], 0, 8, 12, 8, "bytes"),
        ts_panel("Delivery Attempt Count", [
            cw("A","AWS/SNS","NumberOfNotificationsFailed","Sum"),
        ], 12, 8, 12, 8),
    ])


def aws_kinesis():
    return dash("AWS Kinesis", "kinesis", [
        ts_panel("Get Records — Success / Bytes", [
            cw("A","AWS/Kinesis","GetRecords.Success","Average",label="Success"),
            cw("B","AWS/Kinesis","GetRecords.Bytes","Average",label="Bytes"),
        ], 0, 0, 12, 8),
        ts_panel("Get Records Latency / Iterator Age", [
            cw("A","AWS/Kinesis","GetRecords.IteratorAgeMilliseconds","Average",label="Iterator Age"),
            cw("B","AWS/Kinesis","GetRecords.Latency","Average",label="Latency"),
        ], 12, 0, 12, 8, "ms"),
        ts_panel("Put Record — Success / Bytes", [
            cw("A","AWS/Kinesis","PutRecord.Success","Average",label="Success"),
            cw("B","AWS/Kinesis","PutRecord.Bytes","Average",label="Bytes"),
        ], 0, 8, 12, 8),
        ts_panel("Put Records — Success / Bytes", [
            cw("A","AWS/Kinesis","PutRecords.Success","Average",label="Success"),
            cw("B","AWS/Kinesis","PutRecords.Bytes","Average",label="Bytes"),
        ], 12, 8, 12, 8),
        ts_panel("Read / Write Provisioned Throughput Exceeded", [
            cw("A","AWS/Kinesis","ReadProvisionedThroughputExceeded","Average",label="Read"),
            cw("B","AWS/Kinesis","WriteProvisionedThroughputExceeded","Average",label="Write"),
        ], 0, 16, 12, 8),
        ts_panel("Incoming Records / Bytes", [
            cw("A","AWS/Kinesis","IncomingRecords","Sum",label="Records"),
            cw("B","AWS/Kinesis","IncomingBytes","Sum",label="Bytes"),
        ], 12, 16, 12, 8),
    ])


def aws_cloudfront():
    return dash("AWS CloudFront", "cloudfront", [
        ts_panel("Requests", [
            cw("A","AWS/CloudFront","Requests","Sum"),
        ], 0, 0, 8, 8),
        ts_panel("Bytes Downloaded / Uploaded", [
            cw("A","AWS/CloudFront","BytesDownloaded","Sum",label="Downloaded"),
            cw("B","AWS/CloudFront","BytesUploaded","Sum",label="Uploaded"),
        ], 8, 0, 8, 8, "bytes"),
        ts_panel("4xx / 5xx Error Rate", [
            cw("A","AWS/CloudFront","4xxErrorRate","Average",label="4xx"),
            cw("B","AWS/CloudFront","5xxErrorRate","Average",label="5xx"),
            cw("C","AWS/CloudFront","TotalErrorRate","Average",label="Total"),
        ], 16, 0, 8, 8, "percent"),
        ts_panel("Cache Hit Rate", [
            cw("A","AWS/CloudFront","CacheHitRate","Average"),
        ], 0, 8, 12, 8, "percent"),
        ts_panel("Origin Latency", [
            cw("A","AWS/CloudFront","OriginLatency","Average"),
        ], 12, 8, 12, 8, "ms"),
    ])


def aws_alb():
    return dash("AWS Application Load Balancer", "alb", [
        ts_panel("Request Count", [
            cw("A","AWS/ApplicationELB","RequestCount","Sum"),
        ], 0, 0, 8, 8),
        ts_panel("Target Response Time", [
            cw("A","AWS/ApplicationELB","TargetResponseTime","Average",label="avg"),
            cw("B","AWS/ApplicationELB","TargetResponseTime","p95",label="p95"),
        ], 8, 0, 8, 8, "s"),
        ts_panel("Healthy / Unhealthy Host Count", [
            cw("A","AWS/ApplicationELB","HealthyHostCount","Average",label="Healthy"),
            cw("B","AWS/ApplicationELB","UnHealthyHostCount","Average",label="Unhealthy"),
        ], 16, 0, 8, 8),
        ts_panel("HTTP 2xx / 4xx / 5xx", [
            cw("A","AWS/ApplicationELB","HTTPCode_Target_2XX_Count","Sum",label="2xx"),
            cw("B","AWS/ApplicationELB","HTTPCode_Target_4XX_Count","Sum",label="4xx"),
            cw("C","AWS/ApplicationELB","HTTPCode_Target_5XX_Count","Sum",label="5xx"),
        ], 0, 8, 12, 8),
        ts_panel("ELB 5xx Errors", [
            cw("A","AWS/ApplicationELB","HTTPCode_ELB_5XX_Count","Sum"),
        ], 12, 8, 12, 8),
        ts_panel("Processed / Consumed LCUs", [
            cw("A","AWS/ApplicationELB","ProcessedBytes","Sum",label="Bytes"),
            cw("B","AWS/ApplicationELB","ConsumedLCUs","Average",label="LCUs"),
        ], 0, 16, 12, 8, "bytes"),
        ts_panel("Active / New Connections", [
            cw("A","AWS/ApplicationELB","ActiveConnectionCount","Average",label="Active"),
            cw("B","AWS/ApplicationELB","NewConnectionCount","Sum",label="New"),
        ], 12, 16, 12, 8),
    ])


def aws_states():
    return dash("AWS Step Functions", "stepfunctions", [
        ts_panel("Executions Started / Succeeded / Failed", [
            cw("A","AWS/States","ExecutionsStarted","Sum",label="Started"),
            cw("B","AWS/States","ExecutionsSucceeded","Sum",label="Succeeded"),
            cw("C","AWS/States","ExecutionsFailed","Sum",label="Failed"),
        ], 0, 0, 12, 8),
        ts_panel("Executions Throttled / Aborted / Timed Out", [
            cw("A","AWS/States","ExecutionsThrottled","Sum",label="Throttled"),
            cw("B","AWS/States","ExecutionsAborted","Sum",label="Aborted"),
            cw("C","AWS/States","ExecutionsTimedOut","Sum",label="Timed Out"),
        ], 12, 0, 12, 8),
        ts_panel("Execution Time", [
            cw("A","AWS/States","ExecutionTime","Average",label="avg"),
            cw("B","AWS/States","ExecutionTime","Maximum",label="max"),
        ], 0, 8, 12, 8, "ms"),
        ts_panel("Activity Schedule / Run Time", [
            cw("A","AWS/States","ActivityScheduleTime","Average",label="Schedule"),
            cw("B","AWS/States","ActivityRunTime","Average",label="Run"),
        ], 12, 8, 12, 8, "ms"),
    ])


def aws_cognito():
    return dash("AWS Cognito", "cognito", [
        ts_panel("Sign-in / Sign-up Successes", [
            cw("A","AWS/Cognito","SignInSuccesses","Sum",label="Sign-in"),
            cw("B","AWS/Cognito","SignUpSuccesses","Sum",label="Sign-up"),
        ], 0, 0, 12, 8),
        ts_panel("Token Refresh Successes", [
            cw("A","AWS/Cognito","TokenRefreshSuccesses","Sum"),
        ], 12, 0, 12, 8),
        ts_panel("Federation Successes", [
            cw("A","AWS/Cognito","FederationSuccesses","Sum"),
        ], 0, 8, 12, 8),
        ts_panel("Request Rate", [
            cw("A","AWS/Cognito","SignUpSuccesses","Sum",label="SignUp"),
            cw("B","AWS/Cognito","SignInSuccesses","Sum",label="SignIn"),
            cw("C","AWS/Cognito","TokenRefreshSuccesses","Sum",label="Refresh"),
        ], 12, 8, 12, 8),
    ])


def aws_codebuild():
    return dash("AWS CodeBuild", "codebuild", [
        ts_panel("Builds Succeeded / Failed", [
            cw("A","AWS/CodeBuild","SucceededBuilds","Sum",label="Succeeded"),
            cw("B","AWS/CodeBuild","FailedBuilds","Sum",label="Failed"),
        ], 0, 0, 12, 8),
        ts_panel("Build Duration", [
            cw("A","AWS/CodeBuild","Duration","Average",label="avg"),
            cw("B","AWS/CodeBuild","Duration","Maximum",label="max"),
        ], 12, 0, 12, 8, "s"),
        ts_panel("Queue Duration", [
            cw("A","AWS/CodeBuild","QueuedDuration","Average",label="avg"),
        ], 0, 8, 12, 8, "s"),
        ts_panel("CPU / Memory Utilized", [
            cw("A","AWS/CodeBuild","CPUUtilized","Average",label="CPU"),
            cw("B","AWS/CodeBuild","MemoryUtilized","Average",label="Memory"),
        ], 12, 8, 12, 8, "percent"),
    ])


def aws_efs():
    return dash("AWS EFS", "efs", [
        ts_panel("Client Connections", [
            cw("A","AWS/EFS","ClientConnections","Sum"),
        ], 0, 0, 12, 8),
        ts_panel("Data Read / Write IO Bytes", [
            cw("A","AWS/EFS","DataReadIOBytes","Average",label="Read"),
            cw("B","AWS/EFS","DataWriteIOBytes","Average",label="Write"),
        ], 12, 0, 12, 8, "bytes"),
        ts_panel("Metered IO Bytes", [
            cw("A","AWS/EFS","MeteredIOBytes","Average"),
        ], 0, 8, 12, 8, "bytes"),
        ts_panel("Percent IO Limit", [
            cw("A","AWS/EFS","PercentIOLimit","Average"),
        ], 12, 8, 12, 8, "percent"),
        ts_panel("Burst Credit Balance", [
            cw("A","AWS/EFS","BurstCreditBalance","Average"),
        ], 0, 16, 12, 8),
        ts_panel("Storage Bytes", [
            cw("A","AWS/EFS","StorageBytes","Average"),
        ], 12, 16, 12, 8, "bytes"),
    ])


def aws_ses():
    return dash("AWS SES", "ses", [
        ts_panel("Sends / Deliveries / Bounces", [
            cw("A","AWS/SES","Send","Sum",label="Sends"),
            cw("B","AWS/SES","Delivery","Sum",label="Delivered"),
            cw("C","AWS/SES","Bounce","Sum",label="Bounced"),
        ], 0, 0, 12, 8),
        ts_panel("Complaints / Rejects", [
            cw("A","AWS/SES","Complaint","Sum",label="Complaints"),
            cw("B","AWS/SES","Reject","Sum",label="Rejects"),
        ], 12, 0, 12, 8),
        ts_panel("Rendering Failures", [
            cw("A","AWS/SES","RenderingFailure","Sum"),
        ], 0, 8, 12, 8),
        ts_panel("Open / Click Rate", [
            cw("A","AWS/SES","Open","Sum",label="Opens"),
            cw("B","AWS/SES","Click","Sum",label="Clicks"),
        ], 12, 8, 12, 8),
    ])


def aws_waf():
    return dash("AWS WAF", "waf", [
        ts_panel("Allowed / Blocked Requests", [
            cw("A","AWS/WAFV2","AllowedRequests","Sum",label="Allowed"),
            cw("B","AWS/WAFV2","BlockedRequests","Sum",label="Blocked"),
        ], 0, 0, 12, 8),
        ts_panel("Counted Requests", [
            cw("A","AWS/WAFV2","CountedRequests","Sum"),
        ], 12, 0, 12, 8),
        ts_panel("Passed / Challenged Requests", [
            cw("A","AWS/WAFV2","PassedRequests","Sum",label="Passed"),
            cw("B","AWS/WAFV2","ChallengeRequests","Sum",label="Challenged"),
        ], 0, 8, 12, 8),
    ])


def aws_emr():
    return dash("AWS EMR", "emr", [
        ts_panel("Apps Running / Pending / Completed", [
            cw("A","AWS/ElasticMapReduce","AppsRunning","Average",label="Running"),
            cw("B","AWS/ElasticMapReduce","AppsPending","Average",label="Pending"),
            cw("C","AWS/ElasticMapReduce","AppsCompleted","Sum",label="Completed"),
        ], 0, 0, 12, 8),
        ts_panel("Apps Failed / Killed", [
            cw("A","AWS/ElasticMapReduce","AppsFailed","Sum",label="Failed"),
            cw("B","AWS/ElasticMapReduce","AppsKilled","Sum",label="Killed"),
        ], 12, 0, 12, 8),
        ts_panel("Core / Task Nodes Running", [
            cw("A","AWS/ElasticMapReduce","CoreNodesRunning","Average",label="Core"),
            cw("B","AWS/ElasticMapReduce","TaskNodesRunning","Average",label="Task"),
        ], 0, 8, 12, 8),
        ts_panel("HDFS Utilization / Bytes Read", [
            cw("A","AWS/ElasticMapReduce","HDFSUtilization","Average",label="Utilization %"),
            cw("B","AWS/ElasticMapReduce","HdfsBytesRead","Sum",label="Bytes Read"),
        ], 12, 8, 12, 8),
        ts_panel("Map / Reduce Progress", [
            cw("A","AWS/ElasticMapReduce","RunningMapTasks","Average",label="Map"),
            cw("B","AWS/ElasticMapReduce","RunningReduceTasks","Average",label="Reduce"),
        ], 0, 16, 12, 8),
    ])


# ─── Main ─────────────────────────────────────────────────────────────────────

ALL_DASHBOARDS = [
    ("EC2",                    aws_ec2),
    ("Lambda",                 aws_lambda),
    ("SQS",                    aws_sqs),
    ("DynamoDB",               aws_dynamodb),
    ("S3",                     aws_s3),
    ("RDS",                    aws_rds),
    ("ElastiCache",            aws_elasticache),
    ("ECS",                    aws_ecs),
    ("API Gateway",            aws_apigateway),
    ("SNS",                    aws_sns),
    ("Kinesis",                aws_kinesis),
    ("CloudFront",             aws_cloudfront),
    ("Application LB",         aws_alb),
    ("Step Functions",         aws_states),
    ("Cognito",                aws_cognito),
    ("CodeBuild",              aws_codebuild),
    ("EFS",                    aws_efs),
    ("SES",                    aws_ses),
    ("WAF",                    aws_waf),
    ("EMR",                    aws_emr),
]


def main():
    console.print("\n[bold cyan]Ministack → Grafana: AWS Resources Dashboards[/bold cyan]\n")

    with console.status("[cyan]Creating folder 'AWS Resources'…[/cyan]"):
        folder_uid = get_or_create_folder("AWS Resources")
    console.print(f"[green]✓[/green] Folder ready  [dim](uid={folder_uid})[/dim]")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("Creating dashboards…", total=len(ALL_DASHBOARDS))
        for name, builder in ALL_DASHBOARDS:
            prog.update(task, description=f"[cyan]{name}[/cyan]")
            try:
                d = builder()
                r = push_dashboard(d, folder_uid)
                results.append((name, "ok", r.get("url","")))
            except Exception as e:
                results.append((name, "error", str(e)))
            prog.advance(task)

    console.print()
    ok = [r for r in results if r[1]=="ok"]
    err= [r for r in results if r[1]=="error"]

    for name, status, url in ok:
        console.print(f"  [green]✓[/green] {name:25s}  {GRAFANA_URL}{url}")
    for name, status, msg in err:
        console.print(f"  [red]✗[/red] {name:25s}  {msg}")

    console.print(f"\n[bold green]{len(ok)}/{len(ALL_DASHBOARDS)} dashboards created[/bold green] "
                  f"in folder [cyan]AWS Resources[/cyan]\n")


if __name__ == "__main__":
    main()
