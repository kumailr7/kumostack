#!/usr/bin/env python3
"""
Snapchat Architecture Simulation — KumoStack Edition
=====================================================
Simulates the full Snap data-flow at small scale using real AWS API calls
against a local KumoStack instance.

Architecture exercised:
  iOS/Android → EKS Gateway → Media Service → S3 + CloudFront
                            → MCS           → DynamoDB  (message state)
                            → Friend Graph  → ElastiCache + DynamoDB
                            → Snap DB       → DynamoDB  (snap metadata)

Usage:
  python3 simulate.py           # run full demo
  python3 simulate.py --reset   # tear down then re-run
  python3 simulate.py --teardown # tear down only

Requires: pip install boto3
KumoStack must be running: docker compose up -d
"""

import argparse, io, json, sys, time, uuid, zipfile
import boto3
from botocore.exceptions import ClientError

# ── Config ────────────────────────────────────────────────────────────────────

ENDPOINT = "http://localhost:4566"
REGION   = "us-east-1"
ACCOUNT  = "000000000000"

BUCKET        = "snap-media-demo"
TBL_MESSAGES  = "snap-mcs-messages"     # MCS — message delivery state
TBL_METADATA  = "snap-snap-metadata"    # Snap DB — per-snap info
TBL_FRIENDS   = "snap-friend-graph"     # Friend Graph — social graph cache
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
    print(f"    {DIM}{label:<20}{RESET}{BOLD}{value}{RESET}")


# ── boto3 clients ─────────────────────────────────────────────────────────────

def c(service):
    return boto3.client(service, **COMMON)

s3     = c("s3")
ddb    = c("dynamodb")
ec     = c("elasticache")
eks    = c("eks")
cf     = c("cloudfront")
lam    = c("lambda")
iam    = c("iam")


# ── Lambda source — microservice handlers ─────────────────────────────────────
# Each Lambda represents one EKS microservice pod.
# Embedded as in-memory zips so the script is self-contained.

def _zip(code: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.py", code)
    return buf.getvalue()


MEDIA_SERVICE_CODE = """
import json, boto3, os
ENDPOINT = os.environ["AWS_ENDPOINT_URL"]
BUCKET   = os.environ["MEDIA_BUCKET"]

def handler(event, context):
    body     = json.loads(event.get("body") or "{}")
    snap_id  = body["snapId"]
    sender   = body["from"]
    recipient = body["to"]
    s3 = boto3.client("s3", endpoint_url=ENDPOINT, region_name="us-east-1",
                      aws_access_key_id="test", aws_secret_access_key="test")
    payload = f"SNAP|id={snap_id}|from={sender}|to={recipient}".encode()
    s3.put_object(Bucket=BUCKET, Key=f"snaps/{snap_id}.jpg",
                  Body=payload, ContentType="image/jpeg",
                  Metadata={"sender": sender, "recipient": recipient})
    return {"statusCode": 200,
            "body": json.dumps({"snapId": snap_id,
                                "mediaKey": f"snaps/{snap_id}.jpg",
                                "sizeBytes": len(payload)})}
"""

MCS_CODE = """
import json, boto3, os, time
ENDPOINT = os.environ["AWS_ENDPOINT_URL"]
TBL      = os.environ["MCS_TABLE"]

def handler(event, context):
    body   = json.loads(event.get("body") or "{}")
    action = body.get("action", "send")
    ddb    = boto3.client("dynamodb", endpoint_url=ENDPOINT, region_name="us-east-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    if action == "send":
        ddb.put_item(TableName=TBL, Item={
            "messageId": {"S": body["messageId"]},
            "snapId":    {"S": body["snapId"]},
            "from":      {"S": body["from"]},
            "to":        {"S": body["to"]},
            "state":     {"S": "DELIVERED"},
            "sentAt":    {"N": str(int(time.time()))},
            "expiresAt": {"N": str(int(time.time()) + 86400)},
        })
        return {"statusCode": 200, "body": json.dumps({"state": "DELIVERED"})}
    elif action == "open":
        ddb.update_item(TableName=TBL,
            Key={"messageId": {"S": body["messageId"]}},
            UpdateExpression="SET #s = :v",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={":v": {"S": "OPENED"}})
        return {"statusCode": 200, "body": json.dumps({"state": "OPENED"})}
    return {"statusCode": 400, "body": json.dumps({"error": "unknown action"})}
"""

FRIEND_GRAPH_CODE = """
import json, boto3, os
ENDPOINT = os.environ["AWS_ENDPOINT_URL"]
TBL      = os.environ["FRIENDS_TABLE"]

def handler(event, context):
    body   = json.loads(event.get("body") or "{}")
    action = body.get("action", "check")
    ddb    = boto3.client("dynamodb", endpoint_url=ENDPOINT, region_name="us-east-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    if action == "check":
        user1, user2 = body["user1"], body["user2"]
        resp = ddb.get_item(TableName=TBL, Key={"userId": {"S": user1}})
        friends = resp.get("Item", {}).get("friends", {}).get("SS", [])
        return {"statusCode": 200,
                "body": json.dumps({"areFriends": user2 in friends,
                                    "friendCount": len(friends)})}
    elif action == "add":
        user, friend = body["user"], body["friend"]
        try:
            ddb.update_item(TableName=TBL,
                Key={"userId": {"S": user}},
                UpdateExpression="ADD friends :f",
                ExpressionAttributeValues={":f": {"SS": [friend]}})
        except Exception:
            ddb.put_item(TableName=TBL,
                Item={"userId": {"S": user}, "friends": {"SS": [friend]}})
        return {"statusCode": 200, "body": json.dumps({"ok": True})}
    return {"statusCode": 400, "body": json.dumps({"error": "unknown action"})}
"""

SNAPDB_CODE = """
import json, boto3, os, time
ENDPOINT = os.environ["AWS_ENDPOINT_URL"]
TBL      = os.environ["METADATA_TABLE"]

def handler(event, context):
    body   = json.loads(event.get("body") or "{}")
    action = body.get("action", "write")
    ddb    = boto3.client("dynamodb", endpoint_url=ENDPOINT, region_name="us-east-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    if action == "write":
        ddb.put_item(TableName=TBL, Item={
            "snapId":    {"S": body["snapId"]},
            "mediaKey":  {"S": body["mediaKey"]},
            "cdnUrl":    {"S": body["cdnUrl"]},
            "from":      {"S": body["from"]},
            "to":        {"S": body["to"]},
            "ttl":       {"N": str(int(time.time()) + 86400)},
            "sizeBytes": {"N": str(body.get("sizeBytes", 0))},
        })
        return {"statusCode": 200, "body": json.dumps({"ok": True})}
    elif action == "get":
        resp = ddb.get_item(TableName=TBL, Key={"snapId": {"S": body["snapId"]}})
        item = resp.get("Item", {})
        if not item:
            return {"statusCode": 404, "body": json.dumps({"error": "snap not found"})}
        return {"statusCode": 200, "body": json.dumps({
            "snapId":   item["snapId"]["S"],
            "cdnUrl":   item["cdnUrl"]["S"],
            "from":     item["from"]["S"],
            "to":       item["to"]["S"],
        })}
    return {"statusCode": 400, "body": json.dumps({"error": "unknown action"})}
"""

LAMBDAS = {
    "snap-media-service": (MEDIA_SERVICE_CODE, {
        "AWS_ENDPOINT_URL": ENDPOINT,
        "MEDIA_BUCKET":     BUCKET,
    }),
    "snap-mcs": (MCS_CODE, {
        "AWS_ENDPOINT_URL": ENDPOINT,
        "MCS_TABLE":        TBL_MESSAGES,
    }),
    "snap-friend-graph": (FRIEND_GRAPH_CODE, {
        "AWS_ENDPOINT_URL": ENDPOINT,
        "FRIENDS_TABLE":    TBL_FRIENDS,
    }),
    "snap-snapdb": (SNAPDB_CODE, {
        "AWS_ENDPOINT_URL": ENDPOINT,
        "METADATA_TABLE":   TBL_METADATA,
    }),
}


# ── Infrastructure setup ──────────────────────────────────────────────────────

def ensure_role():
    role_name = "snap-lambda-role"
    try:
        r = iam.get_role(RoleName=role_name)
        return r["Role"]["Arn"]
    except ClientError:
        r = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [{
                "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]}),
        )
        return r["Role"]["Arn"]

def setup_s3():
    try:
        s3.head_bucket(Bucket=BUCKET)
        ok(f"S3 bucket '{BUCKET}' ready")
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        ok(f"S3 bucket '{BUCKET}' created")

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
        ok(f"ElastiCache '{EC_CLUSTER_ID}' created (Redis, friend-graph cache)")

def setup_eks():
    try:
        eks.describe_cluster(name=EKS_CLUSTER)
        ok(f"EKS cluster '{EKS_CLUSTER}' ready")
    except ClientError:
        eks.create_cluster(
            name=EKS_CLUSTER,
            version="1.29",
            roleArn=f"arn:aws:iam::{ACCOUNT}:role/snap-eks-role",
            resourcesVpcConfig={
                "subnetIds": ["subnet-snap-001", "subnet-snap-002"],
                "securityGroupIds": ["sg-snap-001"],
                "endpointPublicAccess": True,
            },
        )
        ok(f"EKS cluster '{EKS_CLUSTER}' created (900+ nodes in prod, 1 simulated)")

def setup_cloudfront():
    try:
        dists = cf.list_distributions().get("DistributionList", {}).get("Items", [])
        for d in dists:
            if d.get("Comment") == CF_COMMENT:
                ok(f"CloudFront distribution ready — {d['DomainName']}")
                return d["DomainName"]
    except Exception:
        pass
    resp = cf.create_distribution(DistributionConfig={
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
    ok(f"CloudFront distribution created — {domain}")
    return domain

def setup_lambdas(role_arn):
    for fn_name, (code, env) in LAMBDAS.items():
        try:
            lam.get_function(FunctionName=fn_name)
            ok(f"Lambda '{fn_name}' ready")
        except ClientError:
            lam.create_function(
                FunctionName=fn_name,
                Runtime="python3.12",
                Role=role_arn,
                Handler="index.handler",
                Code={"ZipFile": _zip(code)},
                Environment={"Variables": env},
                Timeout=10,
            )
            ok(f"Lambda '{fn_name}' deployed (EKS microservice pod)")

def invoke(fn_name, payload: dict) -> dict:
    resp = lam.invoke(
        FunctionName=fn_name,
        Payload=json.dumps({"body": json.dumps(payload)}).encode(),
    )
    result = json.loads(resp["Payload"].read())
    return json.loads(result.get("body", "{}"))


# ── Friend seeding ────────────────────────────────────────────────────────────

FRIENDSHIPS = [
    ("alice",   ["bob", "charlie", "diana"]),
    ("bob",     ["alice", "diana"]),
    ("charlie", ["alice"]),
    ("diana",   ["alice", "bob"]),
    # "eve" deliberately has no friends — snap to her will be blocked
]

def seed_friends():
    section("Friend Graph — seeding social graph")
    for user, friends in FRIENDSHIPS:
        for friend in friends:
            invoke("snap-friend-graph", {"action": "add", "user": user, "friend": friend})
        ok(f"{user:8s} ↔  {', '.join(friends)}")
    warn("'eve' has no friends — snaps to her will be blocked")


# ── Core simulation ───────────────────────────────────────────────────────────

def send_snap(sender: str, recipient: str, cf_domain: str):
    section(f"Snap Send  —  {sender.upper()} → {recipient.upper()}")

    # ── 1. Gateway / Friend Graph check ──
    step("EKS Gateway", f"routing to Friend Graph for {sender} ↔ {recipient} check …")
    fg_result = invoke("snap-friend-graph", {"action": "check", "user1": sender, "user2": recipient})
    if not fg_result.get("areFriends"):
        err(f"{sender} and {recipient} are not friends — Gateway blocks this snap")
        return None
    ok(f"Friend Graph hit ({fg_result['friendCount']} friends) — access granted")

    snap_id    = f"snap-{uuid.uuid4().hex[:8]}"
    message_id = f"msg-{uuid.uuid4().hex[:8]}"

    # ── 2. Media Service → S3 ──
    step("Media Service", f"uploading snap {snap_id} to S3 …")
    media_result = invoke("snap-media-service", {
        "snapId": snap_id, "from": sender, "to": recipient,
    })
    media_key  = media_result["mediaKey"]
    size_bytes = media_result["sizeBytes"]
    cdn_url    = f"https://{cf_domain}/{media_key}"
    ok(f"S3 key:    s3://{BUCKET}/{media_key}  ({size_bytes} bytes)")
    ok(f"CDN URL:   {cdn_url}")

    # ── 3. MCS → DynamoDB (message state) ──
    step("MCS", f"writing message state → DynamoDB ({TBL_MESSAGES}) …")
    mcs_result = invoke("snap-mcs", {
        "action": "send", "messageId": message_id,
        "snapId": snap_id, "from": sender, "to": recipient,
    })
    ok(f"Message state: {mcs_result['state']}  (id={message_id})")

    # ── 4. Snap DB → DynamoDB (metadata) ──
    step("Snap DB", f"writing snap metadata → DynamoDB ({TBL_METADATA}) …")
    invoke("snap-snapdb", {
        "action": "write", "snapId": snap_id, "mediaKey": media_key,
        "cdnUrl": cdn_url, "from": sender, "to": recipient,
        "sizeBytes": size_bytes,
    })
    ok(f"Snap metadata stored  (snapId={snap_id}, TTL=24h)")

    return snap_id, message_id, cdn_url


def receive_snap(recipient: str, snap_id: str, message_id: str, cdn_url: str):
    section(f"Snap Receive  —  {recipient.upper()} opens snap {snap_id}")

    # ── 1. Snap DB lookup ──
    step("Snap DB", "fetching snap metadata from DynamoDB …")
    meta = invoke("snap-snapdb", {"action": "get", "snapId": snap_id})
    ok(f"Sender:   {meta['from']}")
    ok(f"CDN URL:  {meta['cdnUrl']}")

    # ── 2. CloudFront → S3 origin fetch ──
    step("CloudFront", "serving media (origin fetch from S3) …")
    obj = s3.get_object(Bucket=BUCKET, Key=f"snaps/{snap_id}.jpg")
    raw = obj["Body"].read().decode()
    ok(f"Media payload: {raw}")

    # ── 3. MCS state update ──
    step("MCS", f"updating message state to OPENED → DynamoDB …")
    result = invoke("snap-mcs", {"action": "open", "messageId": message_id})
    ok(f"Message state: {result['state']}")


# ── Teardown ──────────────────────────────────────────────────────────────────

def teardown():
    section("Teardown — removing all demo resources")
    for fn in LAMBDAS:
        try:
            lam.delete_function(FunctionName=fn)
            ok(f"Lambda '{fn}' deleted")
        except ClientError:
            pass
    for tbl in [TBL_MESSAGES, TBL_METADATA, TBL_FRIENDS]:
        try:
            ddb.delete_table(TableName=tbl)
            ok(f"DynamoDB '{tbl}' deleted")
        except ClientError:
            pass
    try:
        # Delete all S3 objects first
        objs = s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])
        if objs:
            s3.delete_objects(Bucket=BUCKET,
                Delete={"Objects": [{"Key": o["Key"]} for o in objs]})
        s3.delete_bucket(Bucket=BUCKET)
        ok(f"S3 bucket '{BUCKET}' deleted")
    except ClientError:
        pass
    try:
        ec.delete_cache_cluster(CacheClusterId=EC_CLUSTER_ID)
        ok(f"ElastiCache '{EC_CLUSTER_ID}' deleted")
    except ClientError:
        pass
    try:
        eks.delete_cluster(name=EKS_CLUSTER)
        ok(f"EKS cluster '{EKS_CLUSTER}' deleted")
    except ClientError:
        pass
    # CloudFront distributions can't easily be deleted without disabling first
    ok("CloudFront distribution left in place (disable manually if needed)")


# ── Summary ───────────────────────────────────────────────────────────────────

def summary():
    section("Simulation Summary")
    msgs   = ddb.scan(TableName=TBL_MESSAGES, Select="COUNT")["Count"]
    snaps  = ddb.scan(TableName=TBL_METADATA, Select="COUNT")["Count"]
    friends = ddb.scan(TableName=TBL_FRIENDS,  Select="COUNT")["Count"]
    objs   = s3.list_objects_v2(Bucket=BUCKET, Prefix="snaps/").get("KeyCount", 0)

    print()
    kv("S3 media objects",      str(objs))
    kv("DynamoDB messages",     str(msgs))
    kv("DynamoDB snap metadata",str(snaps))
    kv("Friend graph entries",  str(friends))
    print()
    ok(f"{GREEN}{BOLD}Architecture simulation complete!{RESET}")
    print()
    print(f"  {DIM}Inspect the data:{RESET}")
    print(f"    aws dynamodb scan --table-name {TBL_MESSAGES} --endpoint-url {ENDPOINT}")
    print(f"    aws dynamodb scan --table-name {TBL_METADATA} --endpoint-url {ENDPOINT}")
    print(f"    aws s3 ls s3://{BUCKET}/snaps/ --endpoint-url {ENDPOINT}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Snapchat architecture demo on KumoStack")
    ap.add_argument("--reset",    action="store_true", help="Tear down then re-run")
    ap.add_argument("--teardown", action="store_true", help="Tear down only")
    args = ap.parse_args()

    banner("Snapchat Architecture Demo — KumoStack Edition")
    print(f"  {DIM}Small-scale simulation of the 5B Snaps/day architecture{RESET}")
    print(f"  {DIM}Endpoint: {ENDPOINT}{RESET}")

    if args.teardown or args.reset:
        teardown()
        if args.teardown:
            return

    # ── Phase 1: Infrastructure ──────────────────────────────────────────────
    section("Phase 1 — Infrastructure Setup")
    role_arn = ensure_role()
    setup_s3()
    setup_dynamo()
    setup_elasticache()
    setup_eks()
    cf_domain = setup_cloudfront()
    setup_lambdas(role_arn)

    # ── Phase 2: Seed social graph ───────────────────────────────────────────
    seed_friends()

    # ── Phase 3: Simulate snap sends ─────────────────────────────────────────
    section("Phase 3 — Simulating Snap Sends")

    # alice → bob (friends ✓)
    r1 = send_snap("alice", "bob", cf_domain)

    # bob → diana (friends ✓)
    r2 = send_snap("bob", "diana", cf_domain)

    # charlie → diana (NOT friends ✗)
    r3 = send_snap("charlie", "diana", cf_domain)

    # alice → eve (eve has no friends ✗)
    r4 = send_snap("alice", "eve", cf_domain)

    # ── Phase 4: Recipients open their snaps ─────────────────────────────────
    if r1:
        receive_snap("bob",   r1[0], r1[1], r1[2])
    if r2:
        receive_snap("diana", r2[0], r2[1], r2[2])

    # ── Phase 5: Summary ─────────────────────────────────────────────────────
    summary()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n  {RED}ERROR:{RESET} {e}")
        print(f"  {DIM}Is KumoStack running?  docker compose up -d{RESET}")
        sys.exit(1)
