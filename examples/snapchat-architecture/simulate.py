#!/usr/bin/env python3
"""
Snapchat Architecture Simulation — KumoStack Edition
=====================================================
Simulates the full Snap data-flow at small scale using real AWS API calls.
Each "microservice" is a direct boto3 call — exactly what an EKS pod would
do when it handles a request.  No Lambda functions are created, so the Live
Infrastructure view shows the real architecture: EKS → DynamoDB / S3 / CF.

Architecture exercised:
  iOS/Android → EKS Gateway → Media Service  → S3 + CloudFront
                            → MCS            → DynamoDB (message state)
                            → Friend Graph   → ElastiCache + DynamoDB
                            → Snap DB        → DynamoDB (snap metadata)

Usage:
  python3 simulate.py             # run full demo
  python3 simulate.py --reset     # tear down then re-run
  python3 simulate.py --teardown  # tear down only

Requires: pip install boto3
KumoStack must be running: docker compose up -d
"""

import argparse, json, sys, time, uuid
import boto3
from botocore.exceptions import ClientError

# ── Config ────────────────────────────────────────────────────────────────────

ENDPOINT      = "http://localhost:4566"
REGION        = "us-east-1"
ACCOUNT       = "000000000000"

BUCKET        = "snap-media-demo"
TBL_MESSAGES  = "snap-mcs-messages"
TBL_METADATA  = "snap-snap-metadata"
TBL_FRIENDS   = "snap-friend-graph"
EKS_CLUSTER   = "snap-demo-cluster"
EC_CLUSTER_ID = "snap-friend-cache"
CF_COMMENT    = "snap-demo-cdn"

COMMON = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

# ── Pretty printing ───────────────────────────────────────────────────────────

GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def banner(text):
    w = 62
    print(f"\n{BOLD}{'═' * w}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{'═' * w}{RESET}")

def section(title):
    print(f"\n{CYAN}{'─' * 60}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}")

def step(svc, msg):
    print(f"  {DIM}[{svc:16s}]{RESET}  {msg}")

def ok(msg):
    print(f"  {GREEN}✓{RESET}  {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠{RESET}  {msg}")

def err(msg):
    print(f"  {RED}✗{RESET}  {msg}")

def kv(label, value):
    print(f"    {DIM}{label:<22}{RESET}{BOLD}{value}{RESET}")

# ── boto3 clients ─────────────────────────────────────────────────────────────

def c(service):
    return boto3.client(service, **COMMON)

s3_  = c("s3")
ddb  = c("dynamodb")
ec   = c("elasticache")
eks_ = c("eks")
cf_  = c("cloudfront")

# ── Infrastructure setup ──────────────────────────────────────────────────────

def setup_s3():
    try:
        s3_.head_bucket(Bucket=BUCKET)
        ok(f"S3 '{BUCKET}' ready")
    except ClientError:
        s3_.create_bucket(Bucket=BUCKET)
        ok(f"S3 '{BUCKET}' created")

def setup_dynamo():
    for name, pk in [
        (TBL_MESSAGES, "messageId"),
        (TBL_METADATA, "snapId"),
        (TBL_FRIENDS,  "userId"),
    ]:
        try:
            ddb.describe_table(TableName=name)
            ok(f"DynamoDB '{name}' ready")
        except ClientError:
            ddb.create_table(
                TableName=name,
                AttributeDefinitions=[{"AttributeName": pk, "AttributeType": "S"}],
                KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}],
                BillingMode="PAY_PER_REQUEST",
            )
            ok(f"DynamoDB '{name}' created")

def setup_elasticache():
    try:
        ec.describe_cache_clusters(CacheClusterId=EC_CLUSTER_ID)
        ok(f"ElastiCache '{EC_CLUSTER_ID}' ready")
    except ClientError:
        ec.create_cache_cluster(
            CacheClusterId=EC_CLUSTER_ID,
            CacheNodeType="cache.t3.micro",
            Engine="redis",
            NumCacheNodes=1,
        )
        ok(f"ElastiCache '{EC_CLUSTER_ID}' created (Friend Graph cache)")

def setup_eks():
    try:
        eks_.describe_cluster(name=EKS_CLUSTER)
        ok(f"EKS '{EKS_CLUSTER}' ready")
    except ClientError:
        eks_.create_cluster(
            name=EKS_CLUSTER,
            version="1.29",
            roleArn=f"arn:aws:iam::{ACCOUNT}:role/snap-eks-role",
            resourcesVpcConfig={
                "subnetIds": ["subnet-snap-001", "subnet-snap-002"],
                "securityGroupIds": ["sg-snap-001"],
                "endpointPublicAccess": True,
            },
            tags={
                # Tags let the Live Architecture route draw EKS→DynamoDB edges
                "snap:dynamo:mcs":      TBL_MESSAGES,
                "snap:dynamo:metadata": TBL_METADATA,
                "snap:dynamo:friends":  TBL_FRIENDS,
                "snap:s3:media":        BUCKET,
            },
        )
        ok(f"EKS '{EKS_CLUSTER}' created  (900+ nodes in prod, 1 simulated)")

def setup_cloudfront():
    try:
        dists = cf_.list_distributions().get("DistributionList", {}).get("Items", [])
        for d in dists:
            if d.get("Comment") == CF_COMMENT:
                ok(f"CloudFront ready — {d['DomainName']}")
                return d["DomainName"]
    except Exception:
        pass
    resp = cf_.create_distribution(DistributionConfig={
        "CallerReference": f"snap-demo-{int(time.time())}",
        "Comment": CF_COMMENT,
        "Origins": {"Quantity": 1, "Items": [{
            "Id": "snap-s3",
            "DomainName": f"{BUCKET}.s3.amazonaws.com",
            "S3OriginConfig": {"OriginAccessIdentity": ""},
        }]},
        "DefaultCacheBehavior": {
            "TargetOriginId": "snap-s3",
            "ViewerProtocolPolicy": "https-only",
            "ForwardedValues": {
                "QueryString": False, "Cookies": {"Forward": "none"},
                "Headers": {"Quantity": 0},
                "QueryStringCacheKeys": {"Quantity": 0},
            },
            "MinTTL": 0,
            "TrustedSigners": {"Enabled": False, "Quantity": 0},
        },
        "Enabled": True,
    })
    domain = resp["Distribution"]["DomainName"]
    ok(f"CloudFront created — {domain}")
    return domain

def setup():
    section("Phase 1 — Infrastructure Setup")
    setup_s3()
    setup_dynamo()
    setup_elasticache()
    setup_eks()
    return setup_cloudfront()

# ── Friend Graph (EKS pod: Friend Graph service) ──────────────────────────────

FRIENDSHIPS = [
    ("alice",   ["bob", "charlie", "diana"]),
    ("bob",     ["alice", "diana"]),
    ("charlie", ["alice"]),
    ("diana",   ["alice", "bob"]),
]

def seed_friends():
    section("Friend Graph pod — seeding social graph → DynamoDB")
    for user, friends in FRIENDSHIPS:
        ddb.put_item(
            TableName=TBL_FRIENDS,
            Item={"userId": {"S": user}, "friends": {"SS": friends}},
        )
        ok(f"{user:8s} ↔  {', '.join(friends)}")
    warn("'eve' has no friends — snaps to her will be blocked by Gateway")

def are_friends(user1, user2):
    """Friend Graph pod: check social graph in DynamoDB (would be Redis in prod)."""
    resp = ddb.get_item(TableName=TBL_FRIENDS, Key={"userId": {"S": user1}})
    friends = resp.get("Item", {}).get("friends", {}).get("SS", [])
    return user2 in friends, len(friends)

# ── Core simulation ───────────────────────────────────────────────────────────

def send_snap(sender: str, recipient: str, cf_domain: str):
    section(f"Snap Send  —  {sender.upper()} → {recipient.upper()}")

    # ── EKS Gateway: friend-graph check before routing ──
    step("EKS  Gateway",    f"routing → Friend Graph pod: {sender} ↔ {recipient} …")
    friends, count = are_friends(sender, recipient)
    if not friends:
        err(f"Not friends — EKS Gateway blocks this snap")
        return None
    ok(f"Friend Graph hit ({count} friends) — routing allowed")

    snap_id    = f"snap-{uuid.uuid4().hex[:8]}"
    message_id = f"msg-{uuid.uuid4().hex[:8]}"
    now        = int(time.time())
    ttl        = now + 86400

    # ── EKS pod: Media Service → S3 ──
    step("EKS  Media Svc",  f"uploading snap {snap_id} → S3 …")
    payload = f"SNAP|id={snap_id}|from={sender}|to={recipient}".encode()
    s3_.put_object(
        Bucket=BUCKET, Key=f"snaps/{snap_id}.jpg",
        Body=payload, ContentType="image/jpeg",
        Metadata={"sender": sender, "recipient": recipient},
    )
    cdn_url = f"https://{cf_domain}/snaps/{snap_id}.jpg"
    ok(f"S3:      s3://{BUCKET}/snaps/{snap_id}.jpg  ({len(payload)} bytes)")
    ok(f"CDN URL: {cdn_url}")

    # ── EKS pod: MCS → DynamoDB ──
    step("EKS  MCS",        f"recording message state → DynamoDB …")
    ddb.put_item(TableName=TBL_MESSAGES, Item={
        "messageId": {"S": message_id},
        "snapId":    {"S": snap_id},
        "from":      {"S": sender},
        "to":        {"S": recipient},
        "state":     {"S": "DELIVERED"},
        "sentAt":    {"N": str(now)},
        "expiresAt": {"N": str(ttl)},
    })
    ok(f"Message: DELIVERED  (id={message_id})")

    # ── EKS pod: Snap DB → DynamoDB ──
    step("EKS  Snap DB",    f"writing snap metadata → DynamoDB …")
    ddb.put_item(TableName=TBL_METADATA, Item={
        "snapId":    {"S": snap_id},
        "mediaKey":  {"S": f"snaps/{snap_id}.jpg"},
        "cdnUrl":    {"S": cdn_url},
        "from":      {"S": sender},
        "to":        {"S": recipient},
        "ttl":       {"N": str(ttl)},
        "sizeBytes": {"N": str(len(payload))},
    })
    ok(f"Metadata stored  (snapId={snap_id}, TTL=24h)")

    return snap_id, message_id, cdn_url


def receive_snap(recipient: str, snap_id: str, message_id: str):
    section(f"Snap Receive  —  {recipient.upper()} opens {snap_id}")

    # ── EKS pod: Snap DB lookup ──
    step("EKS  Snap DB",   "fetching metadata → DynamoDB …")
    meta = ddb.get_item(TableName=TBL_METADATA, Key={"snapId": {"S": snap_id}}).get("Item", {})
    ok(f"Sender:  {meta['from']['S']}")
    ok(f"CDN URL: {meta['cdnUrl']['S']}")

    # ── CloudFront → S3 origin fetch ──
    step("CloudFront",     "serving media (origin fetch → S3) …")
    obj  = s3_.get_object(Bucket=BUCKET, Key=f"snaps/{snap_id}.jpg")
    body = obj["Body"].read().decode()
    ok(f"Payload: {body}")

    # ── EKS pod: MCS state update ──
    step("EKS  MCS",       "updating message state → OPENED …")
    ddb.update_item(
        TableName=TBL_MESSAGES,
        Key={"messageId": {"S": message_id}},
        UpdateExpression="SET #s = :v",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":v": {"S": "OPENED"}},
    )
    ok("Message state: OPENED")

# ── Teardown ──────────────────────────────────────────────────────────────────

def teardown():
    section("Teardown — removing demo resources")
    for tbl in [TBL_MESSAGES, TBL_METADATA, TBL_FRIENDS]:
        try:
            ddb.delete_table(TableName=tbl)
            ok(f"DynamoDB '{tbl}' deleted")
        except ClientError:
            pass
    try:
        objs = s3_.list_objects_v2(Bucket=BUCKET).get("Contents", [])
        if objs:
            s3_.delete_objects(Bucket=BUCKET,
                Delete={"Objects": [{"Key": o["Key"]} for o in objs]})
        s3_.delete_bucket(Bucket=BUCKET)
        ok(f"S3 '{BUCKET}' deleted")
    except ClientError:
        pass
    try:
        ec.delete_cache_cluster(CacheClusterId=EC_CLUSTER_ID)
        ok(f"ElastiCache '{EC_CLUSTER_ID}' deleted")
    except ClientError:
        pass
    try:
        eks_.delete_cluster(name=EKS_CLUSTER)
        ok(f"EKS '{EKS_CLUSTER}' deleted")
    except ClientError:
        pass
    ok("CloudFront distribution left in place (disable manually if needed)")

# ── Summary ───────────────────────────────────────────────────────────────────

def summary():
    section("Summary")
    msgs   = ddb.scan(TableName=TBL_MESSAGES, Select="COUNT")["Count"]
    snaps  = ddb.scan(TableName=TBL_METADATA, Select="COUNT")["Count"]
    friends = ddb.scan(TableName=TBL_FRIENDS,  Select="COUNT")["Count"]
    objs   = s3_.list_objects_v2(Bucket=BUCKET, Prefix="snaps/").get("KeyCount", 0)
    print()
    kv("S3 media objects",       str(objs))
    kv("DynamoDB messages",      str(msgs))
    kv("DynamoDB snap metadata", str(snaps))
    kv("Friend graph entries",   str(friends))
    print()
    ok(f"{GREEN}{BOLD}Simulation complete!{RESET}")
    print()
    print(f"  {DIM}Inspect:{RESET}")
    print(f"    aws dynamodb scan --table-name {TBL_MESSAGES} --endpoint-url {ENDPOINT}")
    print(f"    aws s3 ls s3://{BUCKET}/snaps/ --endpoint-url {ENDPOINT}")
    print()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset",    action="store_true")
    ap.add_argument("--teardown", action="store_true")
    args = ap.parse_args()

    banner("Snapchat Architecture Demo — KumoStack Edition")
    print(f"  {DIM}EKS microservices + DynamoDB + S3 + CloudFront + ElastiCache{RESET}")
    print(f"  {DIM}Endpoint: {ENDPOINT}{RESET}")

    if args.teardown or args.reset:
        teardown()
        if args.teardown:
            return

    cf_domain = setup()
    seed_friends()

    section("Phase 3 — Simulating Snap Sends")
    r1 = send_snap("alice",   "bob",   cf_domain)
    r2 = send_snap("bob",     "diana", cf_domain)
    send_snap("charlie", "diana", cf_domain)  # blocked — not friends
    send_snap("alice",   "eve",   cf_domain)  # blocked — no friends

    if r1: receive_snap("bob",   *r1[:2])
    if r2: receive_snap("diana", *r2[:2])

    summary()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"\n  {RED}ERROR:{RESET} {e}")
        print(f"  {DIM}Is KumoStack running?  docker compose up -d{RESET}")
        sys.exit(1)
