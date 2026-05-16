#!/usr/bin/env python3
"""
realtime_metrics.py  —  Continuously push live CloudWatch metrics to KumoStack.

Simulates realistic AWS resource activity every INTERVAL seconds so Grafana
dashboards show a live, moving time series without needing real traffic.

Usage:
    python3 scripts/realtime_metrics.py              # default 10s interval
    python3 scripts/realtime_metrics.py --interval 5
    python3 scripts/realtime_metrics.py --interval 10 --once   # push one batch and exit

Press Ctrl+C to stop.
"""

import argparse
import datetime
import json
import math
import os
import random
import subprocess
import sys
import time

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("ERROR: pip install rich", file=sys.stderr)
    sys.exit(1)

ENDPOINT = os.environ.get("MINISTACK_ENDPOINT", "http://localhost:4566")
REGION   = os.environ.get("AWS_DEFAULT_REGION",  "us-east-1")

console = Console()

# Stateful "resource activity" so values change smoothly over time
_state = {
    "ec2_cpu":    [random.uniform(20, 60) for _ in range(3)],
    "sqs_depth":  random.randint(10, 80),
    "lambda_inv": random.randint(30, 120),
    "ddb_rcu":    random.uniform(2, 10),
    "tick":       0,
}


def _put(namespace, metric, unit, value):
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    md = {"MetricName": metric, "Timestamp": ts, "Value": value, "Unit": unit}
    subprocess.run(
        ["aws", "cloudwatch", "put-metric-data",
         "--endpoint-url", ENDPOINT, "--region", REGION,
         "--namespace", namespace,
         "--metric-data", json.dumps([md])],
        capture_output=True,
        env={**os.environ,
             "AWS_ACCESS_KEY_ID": "test",
             "AWS_SECRET_ACCESS_KEY": "test",
             "AWS_DEFAULT_REGION": REGION},
    )


def push_batch():
    t = _state["tick"]

    # EC2 — 3 instances, sinusoidal CPU with noise
    cpus = []
    for i in range(3):
        base = _state["ec2_cpu"][i]
        cpu = max(1, min(99, base + math.sin((t + i * 20) / 8) * 18 + random.gauss(0, 3)))
        _state["ec2_cpu"][i] = cpu
        cpus.append(round(cpu, 2))
    avg_cpu = round(sum(cpus) / len(cpus), 2)
    _put("AWS/EC2", "CPUUtilization", "Percent", avg_cpu)

    # Lambda — spiky invocations
    inv = max(0, int(_state["lambda_inv"] + random.gauss(0, 15) + math.sin(t / 4) * 20))
    _state["lambda_inv"] = max(5, inv)
    err = max(0, int(inv * random.uniform(0, 0.06)))
    dur = round(max(10, random.gauss(115, 25)), 1)
    _put("AWS/Lambda", "Invocations",  "Count",        inv)
    _put("AWS/Lambda", "Errors",       "Count",        err)
    _put("AWS/Lambda", "Duration",     "Milliseconds", dur)

    # SQS — queue depth fluctuates
    depth = _state["sqs_depth"]
    depth = max(0, depth + random.randint(-8, 12))
    _state["sqs_depth"] = depth
    sent = random.randint(0, 20)
    _put("AWS/SQS", "ApproximateNumberOfMessagesVisible", "Count", depth)
    _put("AWS/SQS", "NumberOfMessagesSent",               "Count", sent)

    # DynamoDB
    rcu = round(max(0.5, _state["ddb_rcu"] + random.gauss(0, 1.5)), 2)
    wcu = round(max(0.2, rcu * random.uniform(0.3, 0.8)),            2)
    _state["ddb_rcu"] = rcu
    _put("AWS/DynamoDB", "ConsumedReadCapacityUnits",  "Count", rcu)
    _put("AWS/DynamoDB", "ConsumedWriteCapacityUnits", "Count", wcu)

    _state["tick"] += 1
    return avg_cpu, inv, err, depth, rcu


def make_table(avg_cpu, inv, err, depth, rcu, interval):
    t = Table(title="[bold cyan]KumoStack — Live Metrics[/bold cyan]",
              show_header=True, header_style="bold magenta")
    t.add_column("Namespace",  style="cyan",  width=16)
    t.add_column("Metric",     style="white", width=28)
    t.add_column("Value",      style="green", justify="right", width=12)

    t.add_row("AWS/EC2",      "CPUUtilization (avg)",           f"{avg_cpu:.1f} %")
    t.add_row("AWS/Lambda",   "Invocations",                    str(inv))
    t.add_row("AWS/Lambda",   "Errors",                         Text(str(err), style="red" if err > 0 else "green"))
    t.add_row("AWS/SQS",      "Messages Visible",               str(depth))
    t.add_row("AWS/DynamoDB", "ConsumedReadCapacityUnits",      f"{rcu:.2f}")
    t.add_row("",             "",                               "")
    t.add_row("[dim]next push[/dim]", f"[dim]every {interval}s — Ctrl+C to stop[/dim]", "")
    return t


def main():
    parser = argparse.ArgumentParser(description="Push real-time metrics to KumoStack CloudWatch")
    parser.add_argument("--interval", type=int, default=10, help="Push interval in seconds (default 10)")
    parser.add_argument("--once",     action="store_true",  help="Push one batch and exit")
    args = parser.parse_args()

    if args.once:
        vals = push_batch()
        console.print(make_table(*vals, args.interval))
        return

    console.print(f"\n[bold green]Starting real-time metrics pusher[/bold green] "
                  f"— interval [cyan]{args.interval}s[/cyan], endpoint [cyan]{ENDPOINT}[/cyan]\n")

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            vals = push_batch()
            live.update(make_table(*vals, args.interval))
            time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
