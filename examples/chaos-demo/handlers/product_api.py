"""
product-api Lambda — stores products in DynamoDB.
On failure, publishes the item to SNS so the retry queue can pick it up.
"""
import json
import os
import uuid
import boto3
from botocore.config import Config

ENDPOINT  = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
TABLE     = os.environ.get("TABLE_NAME", "Products")
SNS_TOPIC = os.environ.get("SNS_TOPIC_ARN", "")
REGION    = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# No retries — let chaos faults surface immediately as exceptions
_no_retry = Config(retries={"max_attempts": 1}, connect_timeout=5, read_timeout=5)

_ddb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
    config=_no_retry,
)
_sns = boto3.client(
    "sns",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
    config=_no_retry,
)
_table = _ddb.Table(TABLE)


def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):
    method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    )

    # ── GET /products — list all ──────────────────────────────────────
    if method == "GET":
        resp = _table.scan()
        return _resp(200, {"products": resp.get("Items", []), "count": resp.get("Count", 0)})

    # ── POST /products — create one ───────────────────────────────────
    if method == "POST":
        raw  = event.get("body") or "{}"
        body = json.loads(raw)
        item = {
            "id":    str(uuid.uuid4())[:8],
            "name":  body.get("name", "unnamed"),
            "price": str(body.get("price", "0")),
        }

        try:
            _table.put_item(Item=item)
            return _resp(200, {"status": "stored", "product": item})

        except Exception as exc:
            # ── resilient fallback: publish to SNS for retry ──────────
            if SNS_TOPIC:
                try:
                    _sns.publish(
                        TopicArn=SNS_TOPIC,
                        Message=json.dumps(item),
                        Subject="product-retry",
                    )
                    queue_status = "queued_for_retry"
                except Exception as sns_exc:
                    queue_status = f"queue_failed: {sns_exc}"
            else:
                queue_status = "no_fallback_configured"

            return _resp(500, {
                "status":       queue_status,
                "error":        str(exc),
                "product":      item,
            })

    return _resp(404, {"error": f"unsupported method: {method}"})
