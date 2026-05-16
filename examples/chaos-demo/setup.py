#!/usr/bin/env python3
"""
chaos-demo setup — deploys:
  - DynamoDB table      Products
  - Lambda              product-api       (stores products / falls back to SNS)
  - Lambda              retry-processor   (reads SQS, retries DynamoDB writes)
  - SNS topic           product-failures
  - SQS queue           product-retry-queue
  - SQS → SNS subscription
  - SQS trigger on retry-processor Lambda
  - API Gateway (REST)  Products API  →  product-api

Usage:
  python3 setup.py          # deploy
  python3 setup.py --reset  # tear down then redeploy
"""
import argparse, json, os, sys, time, zipfile, io
import boto3
from botocore.exceptions import ClientError

ENDPOINT = "http://localhost:4566"
REGION   = "us-east-1"
ACCOUNT  = "000000000000"

COMMON = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

ddb      = boto3.client("dynamodb",      **COMMON)
lam      = boto3.client("lambda",        **COMMON)
sns      = boto3.client("sns",           **COMMON)
sqs      = boto3.client("sqs",           **COMMON)
iam      = boto3.client("iam",           **COMMON)
agw      = boto3.client("apigateway",    **COMMON)


# ── helpers ──────────────────────────────────────────────────────────────────

def _zip(filename: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        src = os.path.join(os.path.dirname(__file__), "handlers", filename)
        zf.write(src, filename)
    return buf.getvalue()


def _role_arn() -> str:
    name = "kumostack-lambda-role"
    try:
        return iam.get_role(RoleName=name)["Role"]["Arn"]
    except ClientError:
        pass
    r = iam.create_role(
        RoleName=name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        }),
    )
    iam.attach_role_policy(
        RoleName=name,
        PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess",
    )
    return r["Role"]["Arn"]


def _delete_lambda(name: str):
    try:
        lam.delete_function(FunctionName=name)
        print(f"  deleted lambda {name}")
    except ClientError:
        pass


def _delete_table(name: str):
    try:
        ddb.delete_table(TableName=name)
        waiter = ddb.get_waiter("table_not_exists")
        waiter.wait(TableName=name)
        print(f"  deleted table {name}")
    except ClientError:
        pass


# ── deploy ────────────────────────────────────────────────────────────────────

def deploy():
    role_arn = _role_arn()
    print(f"✓ IAM role: {role_arn}")

    # ── DynamoDB ──────────────────────────────────────────────────────
    try:
        ddb.create_table(
            TableName="Products",
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = ddb.get_waiter("table_exists")
        waiter.wait(TableName="Products")
        print("✓ DynamoDB table: Products")
    except ClientError as e:
        if "ResourceInUseException" in str(e):
            print("✓ DynamoDB table: Products (already exists)")
        else:
            raise

    # ── SNS topic ─────────────────────────────────────────────────────
    topic_resp = sns.create_topic(Name="product-failures")
    topic_arn  = topic_resp["TopicArn"]
    print(f"✓ SNS topic: {topic_arn}")

    # ── SQS queue ─────────────────────────────────────────────────────
    queue_resp = sqs.create_queue(
        QueueName="product-retry-queue",
        Attributes={"VisibilityTimeout": "30", "ReceiveMessageWaitTimeSeconds": "5"},
    )
    queue_url = queue_resp["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    print(f"✓ SQS queue: {queue_url}")

    # allow SNS to send to SQS
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            "Policy": json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "sns.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
                }],
            })
        },
    )

    # ── SNS → SQS subscription ────────────────────────────────────────
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
    print("✓ SNS → SQS subscription")

    # ── Lambda: retry-processor ───────────────────────────────────────
    _delete_lambda("retry-processor")
    retry_fn = lam.create_function(
        FunctionName="retry-processor",
        Runtime="python3.12",
        Role=role_arn,
        Handler="retry_processor.handler",
        Code={"ZipFile": _zip("retry_processor.py")},
        Environment={"Variables": {
            "AWS_ENDPOINT_URL": ENDPOINT,
            "TABLE_NAME": "Products",
        }},
        Timeout=30,
    )
    retry_arn = retry_fn["FunctionArn"]
    print(f"✓ Lambda: retry-processor  ({retry_arn})")

    # SQS event source mapping for retry-processor
    try:
        lam.create_event_source_mapping(
            EventSourceArn=queue_arn,
            FunctionName="retry-processor",
            BatchSize=10,
            Enabled=True,
        )
        print("✓ SQS trigger → retry-processor")
    except ClientError as e:
        if "ResourceConflictException" not in str(e):
            raise
        print("✓ SQS trigger → retry-processor (already mapped)")

    # ── Lambda: product-api ───────────────────────────────────────────
    _delete_lambda("product-api")
    api_fn = lam.create_function(
        FunctionName="product-api",
        Runtime="python3.12",
        Role=role_arn,
        Handler="product_api.handler",
        Code={"ZipFile": _zip("product_api.py")},
        Environment={"Variables": {
            "AWS_ENDPOINT_URL": ENDPOINT,
            "TABLE_NAME": "Products",
            "SNS_TOPIC_ARN": topic_arn,
        }},
        Timeout=30,
    )
    api_fn_arn = api_fn["FunctionArn"]
    print(f"✓ Lambda: product-api       ({api_fn_arn})")

    # ── API Gateway ───────────────────────────────────────────────────
    # delete existing API named "Products API" first
    apis = agw.get_rest_apis()
    for a in apis.get("items", []):
        if a["name"] == "Products API":
            agw.delete_rest_api(restApiId=a["id"])
            time.sleep(1)

    rest = agw.create_rest_api(name="Products API")
    api_id = rest["id"]

    # get root resource
    resources = agw.get_resources(restApiId=api_id)
    root_id   = next(r["id"] for r in resources["items"] if r["path"] == "/")

    # /products resource
    prod_res = agw.create_resource(
        restApiId=api_id, parentId=root_id, pathPart="products"
    )
    prod_id = prod_res["id"]

    lambda_uri = (
        f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31"
        f"/functions/{api_fn_arn}/invocations"
    )

    for method in ("GET", "POST"):
        agw.put_method(
            restApiId=api_id, resourceId=prod_id,
            httpMethod=method, authorizationType="NONE",
        )
        agw.put_integration(
            restApiId=api_id, resourceId=prod_id,
            httpMethod=method, type="AWS_PROXY",
            integrationHttpMethod="POST", uri=lambda_uri,
        )

    agw.create_deployment(restApiId=api_id, stageName="dev")
    api_url = f"{ENDPOINT}/restapis/{api_id}/dev/_user_request_/products"
    print(f"✓ API Gateway: {api_url}")

    # save config for test runner
    config = {
        "api_url":   api_url,
        "api_id":    api_id,
        "topic_arn": topic_arn,
        "queue_url": queue_url,
        "queue_arn": queue_arn,
    }
    with open(os.path.join(os.path.dirname(__file__), ".chaos-demo.json"), "w") as f:
        json.dump(config, f, indent=2)

    print("\n" + "─" * 60)
    print("Setup complete. Run the chaos test:")
    print("  python3 test_chaos.py")
    print("─" * 60)
    return config


def teardown():
    print("Tearing down chaos-demo resources...")
    _delete_lambda("product-api")
    _delete_lambda("retry-processor")
    _delete_table("Products")

    for topic in sns.list_topics().get("Topics", []):
        if "product-failures" in topic["TopicArn"]:
            sns.delete_topic(TopicArn=topic["TopicArn"])
            print(f"  deleted SNS topic {topic['TopicArn']}")

    try:
        url = sqs.get_queue_url(QueueName="product-retry-queue")["QueueUrl"]
        sqs.delete_queue(QueueUrl=url)
        print(f"  deleted SQS queue {url}")
    except ClientError:
        pass

    # remove API
    apis = agw.get_rest_apis()
    for a in apis.get("items", []):
        if a["name"] == "Products API":
            agw.delete_rest_api(restApiId=a["id"])
            print(f"  deleted API Gateway {a['id']}")

    cfg = os.path.join(os.path.dirname(__file__), ".chaos-demo.json")
    if os.path.exists(cfg):
        os.remove(cfg)

    print("Teardown complete.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="tear down then redeploy")
    ap.add_argument("--teardown", action="store_true", help="tear down only")
    args = ap.parse_args()

    if args.teardown:
        teardown()
    elif args.reset:
        teardown()
        time.sleep(1)
        deploy()
    else:
        deploy()
