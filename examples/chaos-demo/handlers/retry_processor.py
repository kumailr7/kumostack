"""
retry-processor Lambda — triggered by SQS.
Reads items that failed during chaos and retries DynamoDB writes.
"""
import json
import os
import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
TABLE    = os.environ.get("TABLE_NAME", "Products")
REGION   = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

_ddb   = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
_table = _ddb.Table(TABLE)


def handler(event, context):
    results = []
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            # SNS wraps the payload in a nested "Message" key
            if "Message" in body:
                item = json.loads(body["Message"])
            else:
                item = body

            _table.put_item(Item=item)
            results.append({"status": "retried_ok", "id": item.get("id"), "name": item.get("name")})

        except Exception as exc:
            results.append({"status": "retry_failed", "error": str(exc)})

    print(json.dumps({"processed": len(results), "results": results}))
    return {"processed": len(results), "results": results}
