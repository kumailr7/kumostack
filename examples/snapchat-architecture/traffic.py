#!/usr/bin/env python3
"""
Snapchat Traffic Generator — KumoStack + Grafana Edition
=========================================================
Hammers the Snapchat architecture at configurable RPS and publishes
CloudWatch metrics so the Grafana dashboard lights up in real time.

Usage:
  python3 traffic.py                  # 20 snaps/sec (default)
  python3 traffic.py --rps 100        # 100 snaps/sec
  python3 traffic.py --rps 500        # Snapchat-scale burst
  python3 traffic.py --rps 50 --chaos # inject random errors

Grafana dashboard: http://localhost:3002  (admin / admin)
Requires: pip install boto3
"""

import argparse, random, sys, threading, time, uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError

# ── Config ────────────────────────────────────────────────────────────────────

ENDPOINT  = "http://localhost:4566"
REGION    = "us-east-1"
NAMESPACE = "Snapchat/Traffic"

BUCKET       = "snap-media-demo"
TBL_MESSAGES = "snap-mcs-messages"
TBL_METADATA = "snap-snap-metadata"
TBL_FRIENDS  = "snap-friend-graph"

COMMON = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

# ── Colours ───────────────────────────────────────────────────────────────────

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; C = "\033[96m"
M = "\033[95m"; B = "\033[94m"; BOLD = "\033[1m"; DIM = "\033[2m"; X = "\033[0m"

# ── Shared counters (thread-safe via GIL for simple increments) ───────────────

class Stats:
    def __init__(self):
        self.sent      = 0
        self.delivered = 0
        self.blocked   = 0
        self.errors    = 0
        self.s3_uploads= 0
        self.ddb_writes= 0
        self.fg_lookups= 0
        self.latencies : deque = deque(maxlen=1000)
        self._lock     = threading.Lock()

    def record(self, delivered: bool, blocked: bool, latency_ms: float,
               s3: int = 0, ddb: int = 0, fg: int = 0, error: bool = False):
        with self._lock:
            self.sent       += 1
            self.delivered  += 1 if delivered else 0
            self.blocked    += 1 if blocked   else 0
            self.errors     += 1 if error     else 0
            self.s3_uploads += s3
            self.ddb_writes += ddb
            self.fg_lookups += fg
            self.latencies.append(latency_ms)

    def snapshot(self):
        with self._lock:
            lats = sorted(self.latencies) if self.latencies else [0]
            return {
                "sent":      self.sent,
                "delivered": self.delivered,
                "blocked":   self.blocked,
                "errors":    self.errors,
                "s3":        self.s3_uploads,
                "ddb":       self.ddb_writes,
                "fg":        self.fg_lookups,
                "p50":       lats[len(lats)//2],
                "p95":       lats[int(len(lats)*0.95)],
                "p99":       lats[int(len(lats)*0.99)],
            }

STATS = Stats()

# ── User pool: mix of friends + strangers ────────────────────────────────────

# Real friends (from simulate.py seed)
FRIEND_PAIRS = [
    ("alice",   "bob"),
    ("bob",     "diana"),
    ("alice",   "charlie"),
    ("alice",   "diana"),
    ("charlie", "alice"),
    ("diana",   "bob"),
]
# Strangers — will always be blocked by the Gateway
STRANGER_PAIRS = [
    ("charlie", "diana"),
    ("alice",   "eve"),
    ("frank",   "alice"),
    ("grace",   "bob"),
    ("henry",   "diana"),
]

def random_snap_pair():
    """70 % friends (delivered), 30 % strangers (blocked)."""
    if random.random() < 0.70:
        return random.choice(FRIEND_PAIRS)
    return random.choice(STRANGER_PAIRS)

# ── Core send logic (runs in thread pool) ────────────────────────────────────

# ── Shared boto3 clients (created once, reused across all threads) ────────────

_DDB = boto3.client("dynamodb", **COMMON)
_S3  = boto3.client("s3",       **COMMON)
_CW  = boto3.client("cloudwatch", **COMMON)

def _are_friends(sender, recipient) -> bool:
    try:
        r = _DDB.get_item(TableName=TBL_FRIENDS, Key={"userId": {"S": sender}})
        return recipient in r.get("Item", {}).get("friends", {}).get("SS", [])
    except Exception:
        return False

def send_one_snap(chaos: bool = False) -> None:
    sender, recipient = random_snap_pair()
    t0 = time.time()

    # ── EKS Gateway: Friend Graph check ──
    is_friend = _are_friends(sender, recipient)
    fg = 1

    if not is_friend:
        ms = (time.time() - t0) * 1000
        STATS.record(delivered=False, blocked=True, latency_ms=ms, fg=fg)
        return

    snap_id    = uuid.uuid4().hex[:10]
    message_id = uuid.uuid4().hex[:10]
    now        = int(time.time())

    try:
        # ── EKS Media Service → S3 ──
        if chaos and random.random() < 0.05:   # 5 % simulated S3 error
            raise ClientError({"Error": {"Code": "InternalError"}}, "PutObject")
        payload = f"SNAP|{snap_id}|{sender}→{recipient}".encode()
        _S3.put_object(Bucket=BUCKET, Key=f"snaps/{snap_id}.jpg",
                       Body=payload, ContentType="image/jpeg")
        s3 = 1

        # ── EKS MCS → DynamoDB ──
        _DDB.put_item(TableName=TBL_MESSAGES, Item={
            "messageId": {"S": message_id}, "snapId": {"S": snap_id},
            "from": {"S": sender}, "to": {"S": recipient},
            "state": {"S": "DELIVERED"}, "sentAt": {"N": str(now)},
        })

        # ── EKS Snap DB → DynamoDB ──
        _DDB.put_item(TableName=TBL_METADATA, Item={
            "snapId":   {"S": snap_id},
            "mediaKey": {"S": f"snaps/{snap_id}.jpg"},
            "from":     {"S": sender}, "to": {"S": recipient},
            "ttl":      {"N": str(now + 86400)},
        })

        ms = (time.time() - t0) * 1000
        STATS.record(delivered=True, blocked=False, latency_ms=ms,
                     s3=s3, ddb=2, fg=fg)

    except Exception:
        ms = (time.time() - t0) * 1000
        STATS.record(delivered=False, blocked=False, latency_ms=ms,
                     fg=fg, error=True)

# ── CloudWatch metric publisher (every 10 s) ──────────────────────────────────

_prev_snap  = {"sent": 0, "delivered": 0, "blocked": 0,
               "s3": 0, "ddb": 0, "fg": 0, "errors": 0}

def _push_cloudwatch():
    now = time.time()
    s   = STATS.snapshot()

    delta = {k: max(0, s[k] - _prev_snap[k])
             for k in _prev_snap}
    _prev_snap.update({k: s[k] for k in _prev_snap})

    lats = sorted(STATS.latencies) if STATS.latencies else [0]
    p50 = lats[len(lats)//2]
    p95 = lats[int(len(lats)*0.95)]
    p99 = lats[int(len(lats)*0.99)]

    d_sent = max(delta["sent"], 1)
    total_ops = delta["s3"] + delta["ddb"] + delta["fg"]

    metrics = [
        # Raw counters
        ("SnapsSent",          delta["sent"],                      "Count"),
        ("SnapsDelivered",     delta["delivered"],                 "Count"),
        ("SnapsBlocked",       delta["blocked"],                   "Count"),
        ("SnapsErrored",       delta["errors"],                    "Count"),
        ("S3Uploads",          delta["s3"],                        "Count"),
        ("DynamoDBWrites",     delta["ddb"],                       "Count"),
        ("FriendGraphLookups", delta["fg"],                        "Count"),
        # Latency (recent window, not averages of averages)
        ("LatencyP50",         p50,                                "Milliseconds"),
        ("LatencyP95",         p95,                                "Milliseconds"),
        ("LatencyP99",         p99,                                "Milliseconds"),
        # Pre-computed rates — avoids CloudWatch math expressions
        ("DeliveryRate",       round(delta["delivered"] / d_sent * 100, 2),   "Percent"),
        ("ErrorRate",          round(delta["errors"]    / d_sent * 100, 2),   "Percent"),
        ("RejectionRate",      round(delta["blocked"]   / d_sent * 100, 2),   "Percent"),
        ("SnapsPerSec",        round(delta["sent"] / 10.0, 2),                "Count/Second"),
        ("TotalOpsPerMin",     total_ops,                                      "Count"),
    ]

    try:
        _CW.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{
                "MetricName": name,
                "Value": float(val),
                "Unit": unit,
                "Timestamp": now,
            } for name, val, unit in metrics],
        )
    except Exception:
        pass   # don't let metric publishing kill the load test

def _cloudwatch_loop(stop_evt: threading.Event):
    while not stop_evt.is_set():
        _push_cloudwatch()
        stop_evt.wait(10)

# ── Live terminal stats ───────────────────────────────────────────────────────

def _print_stats(elapsed: float, rps: float):
    s = STATS.snapshot()
    sr = s["delivered"] / max(s["sent"], 1) * 100
    bar_len = 20
    ok_n  = int(sr / 100 * bar_len)
    bar   = f"{G}{'█' * ok_n}{X}{R}{'░' * (bar_len - ok_n)}{X}"

    print(
        f"\r{BOLD}{C}▸{X} "
        f"{BOLD}{s['sent']:>7,}{X} sent  "
        f"{G}{s['delivered']:>7,}{X} delivered  "
        f"{Y}{s['blocked']:>6,}{X} blocked  "
        f"{R}{s['errors']:>5,}{X} errors  "
        f"│ {bar} {sr:5.1f}%  "
        f"│ p50={B}{s['p50']:.0f}ms{X} p99={M}{s['p99']:.0f}ms{X}  "
        f"│ {DIM}{rps:.0f} rps  {elapsed:.0f}s{X}    ",
        end="", flush=True
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Snapchat traffic generator")
    ap.add_argument("--rps",    type=int,  default=20,
                    help="Target requests per second (default 20)")
    ap.add_argument("--workers",type=int,  default=0,
                    help="Thread-pool size (default = rps * 2)")
    ap.add_argument("--chaos",  action="store_true",
                    help="Inject ~5%% random S3 errors to simulate failures")
    ap.add_argument("--duration",type=int, default=0,
                    help="Stop after N seconds (default: run until Ctrl+C)")
    args = ap.parse_args()

    workers = args.workers or min(args.rps * 2, 200)

    print(f"\n{BOLD}{'═'*70}{X}")
    print(f"{BOLD}  Snapchat Traffic Generator — KumoStack Edition{X}")
    print(f"{'═'*70}{X}")
    print(f"  Target RPS  : {BOLD}{C}{args.rps}{X}")
    print(f"  Workers     : {workers}")
    print(f"  Chaos mode  : {Y+'ON'+X if args.chaos else DIM+'off'+X}")
    print(f"  CloudWatch  : {G}Snapchat/Traffic{X} (namespace)")
    print(f"  Grafana     : {B}http://localhost:3002{X}  →  Snapchat Traffic")
    print(f"  Stop        : Ctrl+C")
    print(f"{'─'*70}")
    print()

    stop_evt = threading.Event()
    cw_thread = threading.Thread(target=_cloudwatch_loop, args=(stop_evt,), daemon=True)
    cw_thread.start()

    interval   = 1.0 / args.rps
    start      = time.time()
    last_print = start
    last_sent  = 0
    actual_rps = 0.0

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while True:
                t_before = time.time()
                pool.submit(send_one_snap, args.chaos)

                # rate-limit: sleep to hit target RPS
                elapsed_send = time.time() - t_before
                sleep_time   = interval - elapsed_send
                if sleep_time > 0:
                    time.sleep(sleep_time)

                now = time.time()
                if now - last_print >= 0.5:
                    sent_delta = STATS.snapshot()["sent"] - last_sent
                    actual_rps  = sent_delta / (now - last_print)
                    last_sent   = STATS.snapshot()["sent"]
                    last_print  = now
                    _print_stats(now - start, actual_rps)

                if args.duration and (time.time() - start) >= args.duration:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        stop_evt.set()
        _push_cloudwatch()   # final flush
        s = STATS.snapshot()
        print(f"\n\n{BOLD}{'─'*70}{X}")
        print(f"  {BOLD}Final stats:{X}")
        print(f"    Snaps sent      : {BOLD}{s['sent']:,}{X}")
        print(f"    Delivered       : {G}{s['delivered']:,}{X}  ({s['delivered']/max(s['sent'],1)*100:.1f}%)")
        print(f"    Blocked         : {Y}{s['blocked']:,}{X}")
        print(f"    Errors          : {R}{s['errors']:,}{X}")
        print(f"    S3 uploads      : {s['s3']:,}")
        print(f"    DynamoDB writes : {s['ddb']:,}")
        print(f"    Latency p50/p99 : {s['p50']:.0f}ms / {s['p99']:.0f}ms")
        print(f"{'─'*70}")
        print(f"  View in Grafana: {B}http://localhost:3002{X} → Snapchat Traffic\n")

if __name__ == "__main__":
    main()
