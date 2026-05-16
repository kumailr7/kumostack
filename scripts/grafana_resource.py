#!/usr/bin/env python3
"""
grafana_resource.py  —  TUI helper: add a Ministack AWS resource to Grafana.

Usage (standalone):
    python3 scripts/grafana_resource.py --service sqs --name my-queue
    python3 scripts/grafana_resource.py --service lambda --name my-fn
    python3 scripts/grafana_resource.py --service dynamodb --name my-table
    python3 scripts/grafana_resource.py --service ec2 --name i-0001
    python3 scripts/grafana_resource.py --service s3 --name my-bucket
    python3 scripts/grafana_resource.py --service elasticache --name my-cluster

Called automatically by bin/awslocal after resource creation.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

try:
    import questionary
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("ERROR: run  pip install questionary rich  first", file=sys.stderr)
    sys.exit(1)

GRAFANA_URL  = os.environ.get("GRAFANA_URL",  "http://localhost:3002")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASS = os.environ.get("GRAFANA_PASS", "admin")
CW_DS_UID    = os.environ.get("GRAFANA_CW_UID",   "afm6kyhcmo0sga")
REGION       = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

console = Console()

# ---------------------------------------------------------------------------
# Datasource panel templates per service
# ---------------------------------------------------------------------------

def _cw_target(refId, namespace, metric, statistic, dimension_key, dimension_val, period="60"):
    dims = {dimension_key: [dimension_val]} if dimension_key else {}
    return {
        "refId": refId,
        "queryMode": "Metrics",
        "metricQueryType": 0,
        "metricEditorMode": 0,
        "region": REGION,
        "namespace": namespace,
        "metricName": metric,
        "statistic": statistic,
        "dimensions": dims,
        "matchExact": bool(dims),
        "period": period,
    }


RESOURCE_TEMPLATES = {
    "sqs": {
        "label": "SQS Queue",
        "panels": lambda name: [
            ("Messages Visible",  "timeseries", "AWS/SQS", "ApproximateNumberOfMessagesVisible", "Average", "QueueName", name, "60"),
            ("Messages Sent/min", "timeseries", "AWS/SQS", "NumberOfMessagesSent",               "Sum",     "QueueName", name, "60"),
            ("Oldest Message Age","timeseries", "AWS/SQS", "ApproximateAgeOfOldestMessage",       "Maximum", "QueueName", name, "60"),
        ],
    },
    "lambda": {
        "label": "Lambda Function",
        "panels": lambda name: [
            ("Invocations",  "timeseries", "AWS/Lambda", "Invocations",  "Sum",     "FunctionName", name, "60"),
            ("Errors",       "timeseries", "AWS/Lambda", "Errors",       "Sum",     "FunctionName", name, "60"),
            ("Duration (ms)","timeseries", "AWS/Lambda", "Duration",     "Average", "FunctionName", name, "60"),
            ("Throttles",    "timeseries", "AWS/Lambda", "Throttles",    "Sum",     "FunctionName", name, "60"),
        ],
    },
    "dynamodb": {
        "label": "DynamoDB Table",
        "panels": lambda name: [
            ("Read Capacity",  "timeseries", "AWS/DynamoDB", "ConsumedReadCapacityUnits",  "Sum",     "TableName", name, "60"),
            ("Write Capacity", "timeseries", "AWS/DynamoDB", "ConsumedWriteCapacityUnits", "Sum",     "TableName", name, "60"),
            ("Throttled Reads","timeseries", "AWS/DynamoDB", "ReadThrottleEvents",         "Sum",     "TableName", name, "60"),
            ("Latency (ms)",   "timeseries", "AWS/DynamoDB", "SuccessfulRequestLatency",   "Average", "TableName", name, "60"),
        ],
    },
    "ec2": {
        "label": "EC2 Instance",
        "panels": lambda name: [
            ("CPU Utilization %", "timeseries", "AWS/EC2", "CPUUtilization",  "Average", "InstanceId", name, "60"),
            ("Network In",        "timeseries", "AWS/EC2", "NetworkIn",        "Sum",     "InstanceId", name, "60"),
            ("Network Out",       "timeseries", "AWS/EC2", "NetworkOut",       "Sum",     "InstanceId", name, "60"),
            ("Disk Read Bytes",   "timeseries", "AWS/EC2", "DiskReadBytes",    "Sum",     "InstanceId", name, "60"),
        ],
    },
    "s3": {
        "label": "S3 Bucket",
        "panels": lambda name: [
            ("Number of Objects",  "timeseries", "AWS/S3", "NumberOfObjects", "Average", "BucketName", name, "86400"),
            ("Bucket Size (bytes)","timeseries", "AWS/S3", "BucketSizeBytes", "Average", "BucketName", name, "86400"),
        ],
    },
    "elasticache": {
        "label": "ElastiCache Cluster",
        "panels": lambda name: [
            ("Curr Connections", "timeseries", "AWS/ElastiCache", "CurrConnections", "Average", "CacheClusterId", name, "60"),
            ("Cache Hits",       "timeseries", "AWS/ElastiCache", "CacheHits",       "Sum",     "CacheClusterId", name, "60"),
            ("Cache Misses",     "timeseries", "AWS/ElastiCache", "CacheMisses",     "Sum",     "CacheClusterId", name, "60"),
            ("Evictions",        "timeseries", "AWS/ElastiCache", "Evictions",       "Sum",     "CacheClusterId", name, "60"),
        ],
    },
}

# ---------------------------------------------------------------------------
# Grafana API helpers
# ---------------------------------------------------------------------------

def _grafana_request(method, path, body=None):
    import base64
    token = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
    url = f"{GRAFANA_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json",
                                           "Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Grafana API {method} {path} → {e.code}: {e.read().decode()}")


def create_dashboard(service, name):
    tmpl = RESOURCE_TEMPLATES[service]
    panel_defs = tmpl["panels"](name)

    panels = []
    for idx, (title, ptype, ns, metric, stat, dim_k, dim_v, period) in enumerate(panel_defs):
        col = (idx % 2) * 12
        row = (idx // 2) * 8
        panels.append({
            "id": idx + 1,
            "title": title,
            "type": ptype,
            "gridPos": {"h": 8, "w": 12, "x": col, "y": row},
            "datasource": {"type": "cloudwatch", "uid": CW_DS_UID},
            "targets": [_cw_target("A", ns, metric, stat, dim_k, dim_v, period)],
        })

    dashboard = {
        "title": f"Ministack — {tmpl['label']}: {name}",
        "tags": ["ministack", service, "auto-generated"],
        "timezone": "browser",
        "refresh": "30s",
        "panels": panels,
        "schemaVersion": 38,
    }
    result = _grafana_request("POST", "/api/dashboards/db",
                               {"dashboard": dashboard, "overwrite": True, "folderId": 0})
    return result.get("url", "")


# ---------------------------------------------------------------------------
# TUI prompt
# ---------------------------------------------------------------------------

def prompt_and_add(service, name, auto=False):
    tmpl = RESOURCE_TEMPLATES.get(service)
    if not tmpl:
        return

    console.print()
    console.print(Panel(
        Text.assemble(
            ("  Resource created\n\n", "bold green"),
            ("  Type : ", "dim"), (tmpl["label"],  "cyan bold"), "\n",
            ("  Name : ", "dim"), (name,            "white bold"), "\n",
        ),
        title="[bold]Ministack[/bold]",
        border_style="green",
        padding=(0, 2),
    ))

    if auto:
        add = True
    else:
        add = questionary.confirm(
            f"Add {tmpl['label']} [{name}] metrics to Grafana?",
            default=True,
        ).ask()

    if not add:
        console.print("[dim]Skipped — no dashboard created.[/dim]\n")
        return

    with console.status("[cyan]Creating Grafana dashboard…[/cyan]"):
        try:
            url = create_dashboard(service, name)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}\n")
            return

    console.print(
        Panel(
            Text.assemble(
                ("  Dashboard ready\n\n", "bold green"),
                ("  ", ""), (f"{GRAFANA_URL}{url}", "cyan underline"), "\n",
            ),
            title="[bold]Grafana[/bold]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Add a Ministack resource dashboard to Grafana (with TUI prompt)"
    )
    parser.add_argument("--service", required=True,
                        choices=list(RESOURCE_TEMPLATES),
                        help="AWS service type")
    parser.add_argument("--name", required=True,
                        help="Resource name / ID")
    parser.add_argument("--yes", action="store_true",
                        help="Skip prompt and add automatically")
    args = parser.parse_args()

    prompt_and_add(args.service, args.name, auto=args.yes)


if __name__ == "__main__":
    main()
