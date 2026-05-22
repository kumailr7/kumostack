# Copyright (c) 2026 KumoStack Contributors
# Copyright (c) 2024 MiniStack Contributors
# Licensed under the MIT License. See LICENSE for details.
# Originally based on MiniStack: https://github.com/Nahuel990/ministack
"""
KumoStack — Local AWS Service Emulator.
Single-port ASGI application on port 4566 (configurable via GATEWAY_PORT).
Routes requests to service handlers based on AWS headers, paths, and query parameters.
Compatible with AWS CLI, boto3, and any AWS SDK via --endpoint-url.
"""

import argparse
import asyncio
import base64
import json
import logging
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import parse_qs, unquote

_MINISTACK_HOST = os.environ.get("MINISTACK_HOST", "localhost")
_MINISTACK_PORT = os.environ.get("GATEWAY_PORT", "4566")

_VERSION = os.environ.get("MINISTACK_VERSION") or "dev"
if _VERSION == "dev":
    try:
        from importlib.metadata import version as _pkg_version

        _VERSION = _pkg_version("kumostack")
    except Exception:
        pass

# Matches host headers like "{apiId}.execute-api.<host>" or "{apiId}.execute-api.<host>:4566"
_EXECUTE_API_RE = re.compile(
    r"^([a-f0-9]{8})\.execute-api\." + re.escape(_MINISTACK_HOST) + r"(?::\d+)?$"
)
# AppSync Events realtime WebSocket: {apiId}.appsync-realtime-api.<anything>[:port].
_APPSYNC_REALTIME_RE = re.compile(r"^([a-z0-9]+)\.appsync-realtime-api\.")
# IoT data plane WebSocket: anything containing ".iot." in the host header.
# Match AWS-shaped IoT hosts only — `iot.<region>.<host>`,
# `data-ats.iot.<region>.<host>`, `data.iot.<region>.<host>`, and the
# account-prefixed endpoint returned by DescribeEndpoint
# (`<prefix>.iot.<region>.<host>`). Anchored at a host-segment boundary
# (start-of-host or after a dot) so custom domains that happen to contain
# `.iot.` as a substring (e.g. an S3 bucket `mybucket.iot.example.com`) are
# not misrouted into the MQTT WebSocket handler.
_IOT_DATA_WS_RE = re.compile(r"(^|\.)iot\.[a-z0-9-]+\.")


def _ws_has_mqtt_subprotocol(ws_headers: dict) -> bool:
    """Check whether the upgrade request advertises an ``mqtt`` subprotocol."""
    raw = ws_headers.get("sec-websocket-protocol", "")
    for proto in (p.strip().lower() for p in raw.split(",") if p.strip()):
        if proto in ("mqtt", "mqttv3.1", "mqttv5"):
            return True
    return False


def _ws_resolve_iot_account_id(scope: dict, ws_headers: dict) -> str:
    """Pick the account ID for an inbound IoT WebSocket upgrade.

    Resolution order:

    1. ``X-Amz-Credential`` query parameter (SigV4-signed WS) — extract the
       access key portion. If it's a 12-digit number, use it as the account.
    2. ``Authorization: AWS4-HMAC-SHA256`` header — same extraction.
    3. Fall back to ``MINISTACK_ACCOUNT_ID`` / ``000000000000``.

    SigV4 signature *verification* is intentionally lax (any
    well-formed credential is accepted); IoT policy enforcement is not yet
    feature. The point here is multi-tenancy isolation, not auth.
    """
    qs = scope.get("query_string", b"").decode("utf-8", errors="replace")
    qp = parse_qs(qs, keep_blank_values=True) if qs else {}

    cred = ""
    raw = qp.get("X-Amz-Credential") or qp.get("x-amz-credential")
    if raw:
        cred = raw[0] if isinstance(raw, list) else raw
    if not cred:
        auth = ws_headers.get("authorization", "")
        m = re.search(r"Credential=([^,/]+)/", auth)
        if m:
            cred = m.group(1)

    access_key = cred.split("/", 1)[0] if cred else ""
    if access_key and re.match(r"^\d{12}$", access_key):
        return access_key
    return os.environ.get("MINISTACK_ACCOUNT_ID", "000000000000")
# Virtual-hosted S3 bucket extraction. AWS-aligned per
# docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html and
# bucketnamingrules.html (HTTP vhost — kumostack is HTTP). Works for any
# endpoint hostname (localhost, kumostack, custom Docker DNS, real AWS
# domains) without hardcoding _MINISTACK_HOST.
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_BUCKET_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.\-]{1,61}[a-z0-9])$")


def _extract_s3_vhost_bucket(host: str):
    """Return the bucket if Host is virtual-hosted-style S3, else None.

    AWS virtual-hosted patterns (all must resolve to a bucket):
      <bucket>.<base-host>                          — SDK default
      <bucket>.s3.<base-host>                       — explicit S3 endpoint
      <bucket>.s3.<region>.<base-host>              — region-qualified
      <bucket>.s3-website.<region>.<base-host>      — static website
      <bucket>.s3-accelerate.<base-host>            — transfer acceleration

    A bare ``<base-host>`` (no leading bucket label) is path-style → None.
    """
    if not host:
        return None
    host = host.strip()
    if not host or host.startswith("["):
        return None
    host = host.lower()
    if ":" in host:
        host = host.rsplit(":", 1)[0]
    if not host or _IPV4_RE.match(host) or "." not in host:
        return None
    candidate, tail = host.split(".", 1)
    if not tail or tail.startswith("."):
        return None
    if not _BUCKET_LABEL_RE.match(candidate):
        return None
    if ".." in candidate or _IPV4_RE.match(candidate):
        return None
    if tail == _MINISTACK_HOST or tail.endswith("." + _MINISTACK_HOST):
        return candidate
    first_tail_segment = tail.split(".", 1)[0]
    if first_tail_segment == "s3" or first_tail_segment.startswith(("s3-", "s3express-")):
        return candidate
    return None
_S3_VHOST_EXCLUDE_RE = re.compile(r"\.(execute-api|alb|emr|efs|elasticache|s3-control|appsync-api|appsync-realtime-api|iot)\.")
_HEALTH_PATHS = ("/_kumostack/health", "/_localstack/health", "/health")
_BODY_METHODS = ("POST", "PUT", "PATCH")
_COGNITO_USERINFO_PATHS = ("/oauth2/userInfo", "/oauth2/userinfo")
_RDS_DATA_PATHS = ("/Execute", "/BeginTransaction", "/CommitTransaction", "/RollbackTransaction", "/BatchExecute")
_S3_CONTROL_PREFIX = "/v20180820/"
_SES_V2_PREFIX = "/v2/email"
_ALB_PATH_PREFIX = "/_alb/"
_NON_S3_VHOST_NAMES = frozenset({
    "s3", "s3-control", "sqs", "sns", "dynamodb", "lambda", "iam", "sts",
    "secretsmanager", "logs", "ssm", "events", "kinesis", "monitoring", "ses",
    "states", "ecs", "rds", "rds-data", "elasticache", "glue", "athena", "airflow",
    "apigateway", "cloudformation", "autoscaling", "codebuild", "transfer", "cur",
    "cloudfront-kvs",
    "appsync-api", "appsync-realtime-api",
})

from kumostack.core.hypercorn_compat import install as _install_hypercorn_compat
from kumostack.core.persistence import PERSIST_STATE, load_state, save_all
from kumostack.core.responses import _12_DIGIT_RE, set_request_account_id, set_request_region
from kumostack.core.router import detect_service, extract_access_key_id, extract_region

# Must run before hypercorn emits its first Expect: 100-continue reply.
# See kumostack/core/hypercorn_compat.py for the rationale (issue #389).
_install_hypercorn_compat()

# ---------------------------------------------------------------------------
# Lazy service loader — modules are imported on first request, not at startup.
# This saves ~20 MB of idle RAM and speeds up boot.
# ---------------------------------------------------------------------------
_loaded_modules: dict = {}

# Execution state of ready.d scripts — surfaced via /_kumostack/health and /_kumostack/ready.
# status: "pending" (not started) | "running" | "completed" (all scripts finished, errors included)
_ready_scripts_state: dict = {
    "status": "pending",
    "total": 0,
    "completed": 0,
    "failed": 0,
}


class _ErrorModule:
    """Stub returned when a service module fails to import."""

    def __init__(self, name: str, error: str):
        self._name = name
        self._error = error

    async def handle_request(self, method, path, headers, body, query_params):
        return (
            500,
            {"Content-Type": "application/json"},
            json.dumps(
                {
                    "__type": "ServiceUnavailable",
                    "message": f"Service module '{self._name}' failed to load: {self._error}",
                }
            ).encode(),
        )

    def get_state(self):
        return {}

    def restore_state(self, data):
        pass

    def load_persisted_state(self, data):
        pass

    def reset(self):
        pass


def _get_module(name: str):
    """Import and cache a service module by short name (e.g. 's3', 'lambda_svc')."""
    mod = _loaded_modules.get(name)
    if mod is None:
        try:
            mod = __import__(f"kumostack.services.{name}", fromlist=["handle_request"])
        except (ModuleNotFoundError, ImportError) as e:
            logger.warning("Service module failed to load: %s - %s", name, e)
            mod = _ErrorModule(name, str(e))
        _loaded_modules[name] = mod
    return mod


def _lazy_handler(module_name: str):
    """Return a callable that lazily imports module_name and delegates to handle_request."""

    async def _handler(method, path, headers, body, query_params):
        mod = _get_module(module_name)
        return await mod.handle_request(method, path, headers, body, query_params)

    return _handler


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kumostack")

# Single source of truth for routable services, their backing modules, and aliases.
SERVICE_REGISTRY = {
    "account": {"module": "account"},
    "acm": {"module": "acm"},
    "backup": {"module": "backup"},
    "batch": {"module": "batch"},
    "apigateway": {"module": "apigateway", "aliases": ("execute-api", "apigatewayv2")},
    "appconfig": {"module": "appconfig"},
    "appconfigdata": {"module": "appconfig"},
    "appsync": {"module": "appsync"},
    "appsync-events": {"module": "appsync_events"},
    "athena": {"module": "athena"},
    "autoscaling": {"module": "autoscaling"},
    "cloudformation": {"module": "cloudformation"},
    "cloudfront": {"module": "cloudfront"},
    "cloudfront-keyvaluestore": {"module": "cloudfront_keyvaluestore"},
    "codebuild": {"module": "codebuild"},
    "cognito-identity": {"module": "cognito"},
    "cognito-idp": {"module": "cognito"},
    "dynamodb": {"module": "dynamodb"},
    "dynamodbstreams": {"module": "dynamodb_streams"},
    "ec2": {"module": "ec2"},
    "ecr": {"module": "ecr"},
    "ecs": {"module": "ecs"},
    "ecs-metadata": {"module": "ecs_metadata"},
    "eks": {"module": "eks"},
    "elasticache": {"module": "elasticache"},
    "elasticfilesystem": {"module": "efs"},
    "elasticloadbalancing": {"module": "alb", "aliases": ("elbv2", "elb")},
    "elasticmapreduce": {"module": "emr"},
    "events": {"module": "eventbridge", "aliases": ("eventbridge",)},
    "firehose": {"module": "firehose", "aliases": ("kinesis-firehose",)},
    "glue": {"module": "glue"},
    "airflow": {"module": "mwaa", "aliases": ("mwaa",)},
    "iam": {"module": "iam"},
    "imds": {"module": "imds"},
    "iot": {"module": "iot"},
    "iot-data": {"module": "iot_data"},
    "kinesis": {"module": "kinesis"},
    "kms": {"module": "kms"},
    "lambda": {"module": "lambda_svc"},
    "logs": {"module": "cloudwatch_logs", "aliases": ("cloudwatch-logs",)},
    "opensearch": {"module": "opensearch", "aliases": ("es", "elasticsearch")},
    "organizations": {"module": "organizations"},
    "monitoring": {"module": "cloudwatch", "aliases": ("cloudwatch",)},
    "rds-data": {"module": "rds_data"},
    "rds": {"module": "rds"},
    "resource-groups": {"module": "resource_groups"},
    "route53": {"module": "route53"},
    "s3": {"module": "s3"},
    "s3files": {"module": "s3files"},
    "scheduler": {"module": "scheduler"},
    "secretsmanager": {"module": "secretsmanager"},
    "servicediscovery": {"module": "servicediscovery"},
    "ses": {"module": "ses"},
    "sns": {"module": "sns"},
    "sqs": {"module": "sqs"},
    "ssm": {"module": "ssm"},
    "states": {"module": "stepfunctions", "aliases": ("step-functions", "stepfunctions")},
    "sts": {"module": "sts"},
    "tagging": {"module": "tagging"},
    "xray": {"module": "xray"},
    "transfer": {"module": "transfer"},
    "waf": {"module": "waf_v1"},
    "waf-regional": {"module": "waf_v1"},
    "wafv2": {"module": "waf"},
    "cloudtrail": {"module": "cloudtrail"},
    "cur": {"module": "cur"},
}

SERVICE_HANDLERS = {
    service_name: _lazy_handler(service_config["module"]) for service_name, service_config in SERVICE_REGISTRY.items()
}

# Maps the on-disk persistence key to the service module name. `save_all`
# (lifespan.shutdown) consumes this. Restore happens at module import time
# in each service via its own `load_state()` call (see e.g. services/sqs.py);
# a small allow-list is also restored centrally by `_load_persisted_state`
# below. Symmetry between save and restore is enforced by
# tests/test_persistence_symmetry.py.
_state_map = {
    "apigateway": "apigateway", "apigateway_v1": "apigateway_v1",
    "sqs": "sqs", "sns": "sns", "ssm": "ssm",
    "secretsmanager": "secretsmanager", "iam": "iam",
    "dynamodb": "dynamodb", "kms": "kms", "eventbridge": "eventbridge",
    "cloudwatch_logs": "cloudwatch_logs", "kinesis": "kinesis",
    "ec2": "ec2", "route53": "route53", "cognito": "cognito",
    "ecr": "ecr", "cloudwatch": "cloudwatch", "s3": "s3",
    "lambda": "lambda_svc", "rds": "rds", "ecs": "ecs",
    "elasticache": "elasticache", "appsync": "appsync",
    "appsync_events": "appsync_events",
    "stepfunctions": "stepfunctions", "alb": "alb",
    "glue": "glue", "mwaa": "mwaa", "efs": "efs", "waf": "waf",
    "athena": "athena", "emr": "emr", "cloudfront": "cloudfront",
    "codebuild": "codebuild", "acm": "acm", "firehose": "firehose",
    "ses": "ses", "ses_v2": "ses_v2",
    "servicediscovery": "servicediscovery", "s3files": "s3files",
    "appconfig": "appconfig", "transfer": "transfer",
    "scheduler": "scheduler", "autoscaling": "autoscaling",
    "eks": "eks", "backup": "backup", "pipes": "pipes",
    "cloudfront_keyvaluestore": "cloudfront_keyvaluestore",
    "resource_groups": "resource_groups",
    "cloudtrail": "cloudtrail", "iot": "iot",
}

SERVICE_NAME_ALIASES = {
    alias: service_name
    for service_name, service_config in SERVICE_REGISTRY.items()
    for alias in service_config.get("aliases", ())
}


def _resolve_port():
    """Resolve gateway port: GATEWAY_PORT > EDGE_PORT > 4566."""
    return os.environ.get("GATEWAY_PORT") or os.environ.get("EDGE_PORT") or "4566"


if os.environ.get("LOCALSTACK_PERSISTENCE") == "1" and os.environ.get("S3_PERSIST") != "1":
    os.environ["S3_PERSIST"] = "1"
    logger.info("LOCALSTACK_PERSISTENCE=1 detected — enabling S3_PERSIST")

_services_env = os.environ.get("SERVICES", "").strip()
if _services_env:
    _requested = {s.strip() for s in _services_env.split(",") if s.strip()}
    _resolved = set()
    for _name in _requested:
        _key = SERVICE_NAME_ALIASES.get(_name, _name)
        if _key in SERVICE_HANDLERS:
            _resolved.add(_key)
        else:
            logger.warning("SERVICES: unknown service '%s' (resolved as '%s') — skipping", _name, _key)
    SERVICE_HANDLERS = {k: v for k, v in SERVICE_HANDLERS.items() if k in _resolved}
    logger.info("SERVICES filter active — enabled: %s", sorted(SERVICE_HANDLERS.keys()))

BANNER = r"""
  __  __ _       _ ____  _             _
 |  \/  (_)_ __ (_) ___|| |_ __ _  ___| | __
 | |\/| | | '_ \| \___ \| __/ _` |/ __| |/ /
 | |  | | | | | | |___) | || (_| | (__|   <
 |_|  |_|_|_| |_|_|____/ \__\__,_|\___|_|\_\

 Local AWS Service Emulator — Port {port}
 Services: S3, SQS, SNS, DynamoDB, Lambda, IAM, STS, SecretsManager, CloudWatch Logs,
          SSM, EventBridge, Kinesis, CloudWatch, SES, SES v2, ACM, WAF v2, Step Functions,
          ECS, RDS, ElastiCache, Glue, Athena, API Gateway, Firehose, Route53,
          Cognito, EC2, EMR, EBS, EFS, ALB/ELBv2, CloudFormation, KMS, ECR, CloudFront,
          AppSync, Cloud Map, S3 Files, RDS Data API, CodeBuild, AppConfig, Transfer, EKS,
          IoT Core
"""


_reset_lock: "asyncio.Lock | None" = None


def _get_reset_lock() -> asyncio.Lock:
    global _reset_lock
    if _reset_lock is None:
        _reset_lock = asyncio.Lock()
    return _reset_lock


# ---------------------------------------------------------------------------
# Request I/O helpers
# ---------------------------------------------------------------------------


def _decode_aws_chunked_body(body: bytes, headers: dict) -> bytes:
    """Decode AWS chunked request bodies and normalize content-encoding headers."""
    sha256_header = headers.get("x-amz-content-sha256", "")
    content_encoding = headers.get("content-encoding", "")
    if not (
        sha256_header.startswith("STREAMING-")
        or "aws-chunked" in content_encoding
        or headers.get("x-amz-decoded-content-length")
    ):
        return body

    decoded = b""
    remaining = body
    while remaining:
        crlf = remaining.find(b"\r\n")
        if crlf == -1:
            break
        chunk_header = remaining[:crlf].decode("ascii", errors="replace")
        size_hex = chunk_header.split(";")[0].strip()
        try:
            chunk_size = int(size_hex, 16)
        except ValueError:
            break
        if chunk_size == 0:
            break
        data_start = crlf + 2
        decoded += remaining[data_start : data_start + chunk_size]
        remaining = remaining[data_start + chunk_size + 2 :]  # skip trailing \r\n

    body = decoded
    if "aws-chunked" in content_encoding:
        encodings = [p.strip() for p in content_encoding.split(",") if p.strip() != "aws-chunked"]
        if encodings:
            headers["content-encoding"] = ", ".join(encodings)
        else:
            headers.pop("content-encoding", None)
    return body


async def _read_request_body(receive, method: str, headers: dict) -> bytes:
    """Read and decode the request body only for methods or headers that can carry one."""
    body = b""
    if headers.get("content-length") or headers.get("transfer-encoding") or method in _BODY_METHODS:
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
    return _decode_aws_chunked_body(body, headers)


async def _send_response(send, status, headers, body):
    """Send ASGI HTTP response."""

    def _encode_header_value(v: str) -> bytes:
        try:
            return v.encode("latin-1")
        except UnicodeEncodeError:
            return v.encode("utf-8")

    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    if "content-length" not in {k.lower() for k in headers}:
        headers["Content-Length"] = str(len(body_bytes))
    header_list = [(k.encode("latin-1"), _encode_header_value(str(v))) for k, v in headers.items()]
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": header_list,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body_bytes,
            "more_body": False,
        }
    )


async def _send_if_handled(send, response) -> bool:
    """Send a response tuple and report whether the request was handled."""
    if response is None:
        return False
    await _send_response(send, *response)
    return True


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# OTLP proxy — forward traces/metrics/logs to Grafana Tempo
# ---------------------------------------------------------------------------

_TEMPO_BASE = os.environ.get("TEMPO_OTLP_URL", "http://kumostack-tempo:4318").rstrip("/")

async def _handle_otlp_proxy(method: str, path: str, headers: dict, body: bytes):
    """Proxy OTLP HTTP requests to Tempo so apps can use KumoStack as their
    OTEL_EXPORTER_OTLP_ENDPOINT without needing a separate collector.

    Supported paths: /v1/traces  /v1/metrics  /v1/logs
    Both application/json and application/x-protobuf are forwarded as-is.
    """
    if method != "POST" or path not in ("/v1/traces", "/v1/metrics", "/v1/logs"):
        return None

    import urllib.request as _urlreq
    ct = headers.get("content-type") or headers.get("Content-Type") or "application/json"
    try:
        req = _urlreq.Request(
            f"{_TEMPO_BASE}{path}",
            data=body,
            headers={"Content-Type": ct},
            method="POST",
        )
        with _urlreq.urlopen(req, timeout=5) as r:
            return r.status, {"Content-Type": "application/json"}, r.read() or b"{}"
    except Exception:
        # Accept the span even if Tempo is unavailable — don't break the app
        return 200, {"Content-Type": "application/json"}, b"{}"


# Tier 1 — Pre-body handlers (no request body needed)
# ---------------------------------------------------------------------------


def _handle_options_request(method: str, request_id: str):
    """Return the standard CORS preflight response when applicable."""
    if method != "OPTIONS":
        return None
    return (
        200,
        {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*",
            "Access-Control-Max-Age": "86400",
            "Content-Length": "0",
            "x-amzn-requestid": request_id,
        },
        b"",
    )


def _handle_health_request(path: str, request_id: str):
    """Return health responses for KumoStack and LocalStack-compatible endpoints."""
    if path not in _HEALTH_PATHS:
        return None
    return (
        200,
        {
            "Content-Type": "application/json",
            "x-amzn-requestid": request_id,
        },
        json.dumps(
            {
                "services": {s: "available" for s in SERVICE_HANDLERS},
                "edition": os.environ.get("MINISTACK_EDITION", "light"),
                "version": _VERSION,
                "ready_scripts": dict(_ready_scripts_state),
            }
        ).encode(),
    )


def _handle_ready_request(path: str, request_id: str):
    """Return readiness state once ready.d scripts have completed."""
    if path != "/_kumostack/ready":
        return None
    ready = _ready_scripts_state["status"] == "completed"
    status = 200 if ready else 503
    return (
        status,
        {
            "Content-Type": "application/json",
            "x-amzn-requestid": request_id,
        },
        json.dumps(dict(_ready_scripts_state)).encode(),
    )


def _handle_unknown_localstack_request(path: str, request_id: str):
    """Return a clear 404 JSON for unrecognised /_localstack/* paths.

    /_localstack/health is already matched by _handle_health_request (included in
    _HEALTH_PATHS), so only unknown paths reach here. This prevents them from
    falling through to the S3 handler and returning confusing NoSuchBucket XML.
    """
    if not path.startswith("/_localstack/"):
        return None
    return (
        404,
        {
            "Content-Type": "application/json",
            "x-amzn-requestid": request_id,
        },
        json.dumps(
            {
                "error": (
                    f"Unknown LocalStack endpoint: {path}. "
                    "KumoStack exposes /_kumostack/health, /_kumostack/ready, and /_kumostack/reset. "
                    "See https://github.com/kumostackorg/kumostack for the full API."
                )
            }
        ).encode(),
    )


def _handle_lambda_download_request(path: str, method: str):
    """Serve KumoStack's Lambda layer and function-code download endpoints."""
    if path.startswith("/_kumostack/lambda-layers/") and method == "GET":
        path_parts = path.split("/")
        if len(path_parts) >= 6 and path_parts[5] == "content" and path_parts[4].isdigit():
            return _get_module("lambda_svc").serve_layer_content(path_parts[3], int(path_parts[4]))

    if path.startswith("/_kumostack/lambda-code/") and method == "GET":
        path_parts = path.split("/")
        if len(path_parts) >= 4:
            return _get_module("lambda_svc").serve_function_code(path_parts[3])
    return None


async def _handle_cognito_get_request(method: str, path: str, headers: dict, query_params: dict):
    """Handle Cognito GET endpoints that do not require request body parsing."""
    if "/.well-known/" in path and method == "GET":
        if path.endswith("/.well-known/jwks.json"):
            pool_id = path.rsplit("/.well-known/jwks.json", 1)[0].lstrip("/")
            if pool_id:
                return _get_module("cognito").well_known_jwks(pool_id)
        elif path.endswith("/.well-known/openid-configuration"):
            pool_id = path.rsplit("/.well-known/openid-configuration", 1)[0].lstrip("/")
            if pool_id:
                region = extract_region(headers) or "us-east-1"
                host = headers.get("host") or headers.get("Host")
                return _get_module("cognito").well_known_openid_configuration(pool_id, region, host)

    if path == "/oauth2/authorize" and method == "GET":
        return _get_module("cognito").handle_oauth2_authorize(method, path, headers, query_params)
    if path in _COGNITO_USERINFO_PATHS and method == "GET":
        return _get_module("cognito").handle_oauth2_userinfo(method, path, headers, b"", query_params)
    if path == "/logout" and method == "GET":
        return _get_module("cognito").handle_logout(method, path, headers, query_params)
    return None


async def _handle_admin_reset(path: str, method: str, query_params: dict):
    """Handle reset requests before request body parsing."""
    if path != "/_kumostack/reset" or method != "POST":
        return None

    async with _get_reset_lock():
        await asyncio.to_thread(_reset_all_state)

    run_init = query_params.get("init", [""])[0] == "1"
    if run_init:
        _run_init_scripts()
        _ready_scripts_state.update({"status": "pending", "total": 0, "completed": 0, "failed": 0})
        asyncio.create_task(_run_ready_scripts())
    return 200, {"Content-Type": "application/json"}, json.dumps({"reset": "ok"}).encode()


async def _handle_ses_messages_request(method: str, path: str, headers: dict, query_params: dict):
    """Handle SES messages inspection endpoint.

    Supports filtering by account via the 'account' query parameter. When provided,
    sets the request context to that account so emails are retrieved from the correct
    AccountScopedDict._sent_emails_list.
    """
    if path != "/_kumostack/ses/messages" or method != "GET":
        return None

    account_id = None
    if "account" in query_params:
        raw_account = query_params["account"]
        account_id = raw_account[0] if isinstance(raw_account, (list, tuple)) else raw_account
        if not _12_DIGIT_RE.match(account_id):
            return (
                400,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "__type": "InvalidAccountID",
                        "message": f"Account ID must be 12 digits, got: {account_id}",
                    }
                ).encode(),
            )

    try:
        mod = _get_module("ses")
        sent_emails_dict = {}
        try:
            all_data = mod._sent_emails.to_dict()
            for (acct, key), val in all_data.items():
                if key == "entries" and isinstance(val, list):
                    sent_emails_dict[acct] = val
        except Exception:
            # Fallback: empty dict on any unexpected shape
            sent_emails_dict = {}

        response = {
            "messages": {
                acct: [
                    {
                        "MessageId": rec["MessageId"],
                        "Source": rec["Source"],
                        "To": rec.get("To", []),
                        "CC": rec.get("CC", []),
                        "BCC": rec.get("BCC", []),
                        "Subject": rec.get("RenderedSubject") or rec.get("Subject", ""),
                        "BodyText": rec.get("RenderedBodyText") or rec.get("BodyText", ""),
                        "BodyHtml": rec.get("RenderedBodyHtml") or rec.get("BodyHtml"),
                        "Timestamp": rec["Timestamp"],
                        "Type": rec["Type"],
                    }
                    for rec in (recs if isinstance(recs, list) else [])
                ]
                for acct, recs in sent_emails_dict.items()
                if account_id is None or acct == account_id
            }
        }
    except Exception as e:
        logger.exception("Error retrieving SES messages: %s", e)
        return 500, {"Content-Type": "application/json"}, json.dumps({"message": str(e)}).encode()

    return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()


async def _handle_pre_body_request(method: str, path: str, headers: dict, query_params: dict, request_id: str):
    """Handle fast-path routes that do not require request body parsing."""
    # OPTIONS on an execute-api host / path MUST flow through apigateway.handle_execute
    # so the API's own corsConfiguration is applied (#406). Skip the generic wildcard
    # preflight in that case.
    host = headers.get("host", "")
    is_execute_api = _parse_execute_api_url(host, path) is not None
    for response in (
        None if is_execute_api else _handle_options_request(method, request_id),
        _handle_health_request(path, request_id),
        _handle_ready_request(path, request_id),
        _handle_unknown_localstack_request(path, request_id),
        _handle_lambda_download_request(path, method),
    ):
        if response is not None:
            return response

    response = await _handle_cognito_get_request(method, path, headers, query_params)
    if response is not None:
        # Cognito's OAuth2/OIDC endpoints (Hosted UI, /oauth2/*, /.well-known/*)
        # are typically called by browser-based OIDC clients and must therefore
        # carry the same `Access-Control-Allow-Origin: *` that every other data
        # plane response gets via _with_data_plane_headers.
        return _with_data_plane_headers(response, request_id)

    response = await _handle_ses_messages_request(method, path, headers, query_params)
    if response is not None:
        return response

    response = _handle_transfer_sftp_ports_request(method, path)
    if response is not None:
        return response

    response = _handle_iot_ca_request(method, path)
    if response is not None:
        return response

    response = await _handle_admin_reset(path, method, query_params)
    if response is not None:
        return response

    response = await _handle_requests_log(path, method, query_params)
    if response is not None:
        return response

    response = await _handle_chaos_request(method, path, b"", query_params)
    if response is not None:
        return response

    response = await _handle_organizations_api(method, path, b"")
    if response is not None:
        return response

    response = await _handle_sts_log_api(method, path)
    if response is not None:
        return response

    response = await _handle_cloudtrail_api(method, path, query_params)
    if response is not None:
        return response

    response = await _handle_chaos_containers(method, path)
    if response is not None:
        return response

    response = await _handle_pumba_jobs(method, path)
    if response is not None:
        return response

    response = await _handle_chaos_region(method, path, b"")
    if response is not None:
        return response

    response = await _handle_k6_request(method, path, b"")
    if response is not None:
        return response

    # X-Ray dashboard helper endpoints
    if path.startswith("/_kumostack/xray"):
        mod = _get_module("xray")
        return await mod.handle_request(method, path, {}, b"", query_params)

    response = await _handle_topology_request(method, path)
    if response is not None:
        return response

    response = await _handle_cost_report(method, path)
    if response is not None:
        return response

    response = await _handle_iam_simulate(method, path, b"")
    if response is not None:
        return response

    return await _handle_chaos_lambda_failure(method, path, b"")


def _handle_iot_ca_request(method: str, path: str):
    """`GET /_ministack/iot/ca.pem` returns the Local CA root certificate.

    Test code and IoT SDKs use this to configure trust for mTLS connections
    to the local broker. The CA is generated lazily on first call.
    """
    if path != "/_ministack/iot/ca.pem" or method != "GET":
        return None
    try:
        from ministack.services import iot

        cert_pem = iot.get_ca_cert_pem()
    except RuntimeError as e:
        return (
            503,
            {"Content-Type": "application/json"},
            json.dumps({"message": str(e)}).encode(),
        )
    except Exception as e:
        return (
            500,
            {"Content-Type": "application/json"},
            json.dumps({"message": str(e)}).encode(),
        )
    return (
        200,
        {
            "Content-Type": "application/x-pem-file",
            "Content-Disposition": "attachment; filename=\"ministack-iot-ca.pem\"",
        },
        cert_pem.encode("utf-8"),
    )


def _handle_transfer_sftp_ports_request(method: str, path: str):
    """`GET /_kumostack/transfer/sftp-ports` returns ``{shared, per_server}``.

    boto3's DescribeServer drops fields not in the AWS spec, so this
    admin endpoint is how tests (and humans) discover which ports
    KumoStack's SFTP listeners ended up on — particularly relevant
    when ``SFTP_PORT_PER_SERVER=1`` allocates ports dynamically from
    ``SFTP_BASE_PORT``.
    """
    if path != "/_kumostack/transfer/sftp-ports" or method != "GET":
        return None
    try:
        from kumostack.services import transfer

        body = {
            "enabled": transfer._sftp_enabled(),
            "port_per_server": transfer._port_per_server(),
            "shared_port": transfer._shared_port() if transfer._sftp_enabled() else None,
            "per_server": dict(transfer._sftp_per_server_ports),
        }
    except Exception as e:
        return 500, {"Content-Type": "application/json"}, json.dumps({"message": str(e)}).encode()
    return 200, {"Content-Type": "application/json"}, json.dumps(body).encode()


# ---------------------------------------------------------------------------
# Tier 2 — Post-body shortcuts (body required, before generic routing)
# ---------------------------------------------------------------------------


async def _handle_cognito_body_request(method: str, path: str, headers: dict, body: bytes, query_params: dict):
    """Handle Cognito routes that require the parsed request body."""
    if path in ("/oauth2/login", "/login") and method == "POST":
        return _get_module("cognito").handle_login_submit(method, path, headers, body, query_params)
    if path == "/oauth2/token" and method == "POST":
        return _get_module("cognito").handle_oauth2_token(method, path, headers, body, query_params)
    if path in _COGNITO_USERINFO_PATHS and method == "POST":
        return _get_module("cognito").handle_oauth2_userinfo(method, path, headers, body, query_params)
    return None


async def _handle_requests_log(path: str, method: str, query_params: dict):
    """GET /_kumostack/requests — return recent API request trace."""
    if path != "/_kumostack/requests" or method != "GET":
        return None
    ct = {"Content-Type": "application/json"}
    limit = int((query_params.get("limit") or [200])[0])
    with _request_log_lock:
        entries = list(_request_log)[-limit:]
    entries.reverse()  # newest first
    return 200, ct, json.dumps(entries).encode()


async def _handle_admin_config_request(path: str, method: str, body: bytes):
    """Apply whitelisted runtime config changes through the admin endpoint."""
    if path != "/_kumostack/config" or method != "POST":
        return None

    allowed_config_keys = {
        "athena.ATHENA_ENGINE",
        "athena.ATHENA_DATA_DIR",
        "stepfunctions._sfn_mock_config",
        "stepfunctions._SFN_WAIT_SCALE",
        "lambda_svc.LAMBDA_EXECUTOR",
        "cloudtrail._recording_enabled",
    }
    try:
        config = json.loads(body) if body else {}
    except json.JSONDecodeError:
        config = {}

    applied = {}
    for key, value in config.items():
        if key not in allowed_config_keys:
            logger.warning("/_kumostack/config: rejected key %s (not in whitelist)", key)
            continue
        if "." not in key:
            continue

        mod_name, var_name = key.rsplit(".", 1)
        try:
            mod = __import__(f"kumostack.services.{mod_name}", fromlist=[var_name])
            if key == "stepfunctions._SFN_WAIT_SCALE":
                try:
                    float_value = float(value)
                except (ValueError, TypeError):
                    logger.warning("/_kumostack/config: invalid SFN_WAIT_SCALE=%r", value)
                    continue
                if not math.isfinite(float_value) or float_value < 0:
                    logger.warning("/_kumostack/config: invalid SFN_WAIT_SCALE=%r", value)
                    continue
                value = float_value
            elif key == "cloudtrail._recording_enabled":
                value = str(value).lower() in ("1", "true", "yes")
            setattr(mod, var_name, value)
            applied[key] = value
        except (ImportError, AttributeError) as e:
            logger.warning("/_kumostack/config: failed to set %s: %s", key, e)
    return 200, {"Content-Type": "application/json"}, json.dumps({"applied": applied}).encode()


async def _handle_post_body_shortcuts(method: str, path: str, headers: dict, body: bytes, query_params: dict, request_id: str):
    """Handle body-dependent routes before the generic service router."""
    # CloudFormation custom resource ResponseURL intercept
    if method == "PUT" and path.startswith("/_kumostack/cfn-response/"):
        token = path[len("/_kumostack/cfn-response/"):]
        try:
            payload = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            payload = {}
        from kumostack.services.cloudformation import custom_resource as _cfn_cr
        if not _cfn_cr.deliver_response(token, payload):
            logging.getLogger("cloudformation").warning(
                "CFN ResponseURL PUT for unknown token %r — ignoring", token
            )
        return 200, {}, b""

    # OTLP proxy — must be before AWS service routing so /v1/traces isn't misrouted
    response = await _handle_otlp_proxy(method, path, headers, body)
    if response is not None:
        return response

    response = await _handle_cognito_body_request(method, path, headers, body, query_params)
    if response is not None:
        # See _handle_pre_body_request: browser-based OIDC clients need CORS.
        return _with_data_plane_headers(response, request_id)

    response = await _handle_admin_config_request(path, method, body)
    if response is not None:
        return response

    response = await _handle_chaos_request(method, path, body, query_params)
    if response is not None:
        return response

    response = await _handle_organizations_api(method, path, body)
    if response is not None:
        return response

    response = await _handle_sts_log_api(method, path)
    if response is not None:
        return response

    response = await _handle_cloudtrail_api(method, path, query_params)
    if response is not None:
        return response

    response = await _handle_chaos_pumba(method, path, body)
    if response is not None:
        return response

    response = await _handle_chaos_region(method, path, body)
    if response is not None:
        return response

    response = await _handle_chaos_lambda_failure(method, path, body)
    if response is not None:
        return response

    response = await _handle_k6_request(method, path, body)
    if response is not None:
        return response

    response = await _handle_iam_simulate(method, path, body)
    if response is not None:
        return response

    return None


# ---------------------------------------------------------------------------
# Tier 3 — Special data-plane handlers (host/path-based routing)
# ---------------------------------------------------------------------------


async def _handle_s3_control_request(path: str, method: str, body: bytes, query_params: dict, request_id: str):
    """Handle S3 Control operations addressed via the /v20180820 path prefix."""
    if not path.startswith(_S3_CONTROL_PREFIX):
        return None

    if path.startswith("/v20180820/tags/"):
        raw_arn = path[len("/v20180820/tags/") :]
        arn = unquote(raw_arn)
        bucket_name = arn.split(":::")[-1].split("/")[0] if ":::" in arn else arn.split("/")[0]

        if method == "GET":
            tags = _get_module("s3")._bucket_tags.get(bucket_name, {})
            tag_members = "".join(f"<member><Key>{k}</Key><Value>{v}</Value></member>" for k, v in tags.items())
            xml_body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<ListTagsForResourceResult xmlns="https://awss3control.amazonaws.com/doc/2018-08-20/">'
                f"<Tags>{tag_members}</Tags>"
                "</ListTagsForResourceResult>"
            ).encode()
            return (
                200,
                {
                    "Content-Type": "application/xml",
                    "x-amzn-requestid": request_id,
                },
                xml_body,
            )

        if method in ("POST", "PUT"):
            # AWS SDK Go v2 (used by terraform-aws-provider v6+) sends
            # TagResource as POST with an XML TagResourceRequest body. Older
            # SDKs used PUT with JSON. Accept both methods + both body shapes
            # so we don't silently drop tags (#447).
            new_tags: dict = {}
            try:
                if body:
                    raw = body if isinstance(body, str) else body.decode("utf-8", errors="replace")
                    stripped = raw.lstrip()
                    if stripped.startswith("<"):
                        # XML: <TagResourceRequest><Tags><Tag><Key>..</Key><Value>..</Value></Tag>...</Tags></TagResourceRequest>
                        from xml.etree.ElementTree import fromstring

                        root = fromstring(raw)

                        def _local(el):
                            t = el.tag
                            return t.split("}")[-1] if "}" in t else t

                        for child in root.iter():
                            if _local(child) != "Tag":
                                continue
                            key_el = next((c for c in child if _local(c) == "Key"), None)
                            val_el = next((c for c in child if _local(c) == "Value"), None)
                            if key_el is not None and key_el.text:
                                new_tags[key_el.text] = (val_el.text or "") if val_el is not None else ""
                    elif stripped.startswith("{"):
                        payload = json.loads(stripped)
                        new_tags = {t["Key"]: t["Value"] for t in payload.get("Tags", [])}
            except Exception as e:
                logger.warning("S3 Control TagResource parse error: %s", e)
            if new_tags:
                existing = _get_module("s3")._bucket_tags.get(bucket_name, {})
                existing.update(new_tags)
                _get_module("s3")._bucket_tags[bucket_name] = existing
            return 204, {"x-amzn-requestid": request_id}, b""

        if method == "DELETE":
            keys_to_remove = query_params.get("tagKeys", [])
            if isinstance(keys_to_remove, str):
                keys_to_remove = [keys_to_remove]
            tags = _get_module("s3")._bucket_tags.get(bucket_name, {})
            for key in keys_to_remove:
                tags.pop(key, None)
            _get_module("s3")._bucket_tags[bucket_name] = tags
            return 204, {"x-amzn-requestid": request_id}, b""

        return (
            200,
            {
                "Content-Type": "application/json",
                "x-amzn-requestid": request_id,
            },
            b"{}",
        )

    return (
        200,
        {
            "Content-Type": "application/json",
            "x-amzn-requestid": request_id,
        },
        b"{}",
    )


async def _handle_rds_data_request(method: str, path: str, headers: dict, body: bytes, query_params: dict):
    """Handle RDS Data API operations before generic routing."""
    if path not in _RDS_DATA_PATHS:
        return None
    return await _get_module("rds_data").handle_request(method, path, headers, body, query_params)


async def _handle_ses_v2_request(method: str, path: str, headers: dict, body: bytes, query_params: dict):
    """Handle SES v2 REST API operations before generic routing."""
    if not path.startswith(_SES_V2_PREFIX):
        return None
    return await _get_module("ses_v2").handle_request(method, path, headers, body, query_params)


def _is_ecr_registry_path(path: str) -> bool:
    """Return True iff `path` is a Docker Registry HTTP API V2 endpoint.

    Shares the `/v2/` prefix with API Gateway v2 (`/v2/apis/...`,
    `/v2/tags/{arn}`), AppSync Events (`/v2/apis`), and SES v2 (`/v2/email/...`).
    Registry paths are distinguished by `/blobs/`, `/manifests/`, or the
    `/tags/list` suffix — none appear in any other `/v2/*` consumer.
    """
    if path in ("/v2", "/v2/", "/v2/_catalog"):
        return True
    if not path.startswith("/v2/") or path.startswith(_SES_V2_PREFIX):
        return False
    return "/blobs/" in path or "/manifests/" in path or path.endswith("/tags/list")


async def _handle_ecr_registry_request(method: str, path: str, headers: dict, body: bytes, query_params: dict):
    """Handle Docker Registry HTTP API V2 requests (`docker push`/`docker pull`).

    Real ECR exposes the V2 protocol on the same endpoint as the AWS API. We
    must run this before the generic router so the path doesn't fall through
    to S3 path-style addressing. The shape check above keeps every other
    `/v2/...` consumer (apigwv2, AppSync Events, SES v2) untouched.
    """
    if not _is_ecr_registry_path(path):
        return None
    return await _get_module("ecr").handle_registry_request(
        method, path, headers, body, query_params
    )


def _parse_execute_api_url(host: str, path: str) -> tuple[str, str, str] | None:
    """Resolve an execute-api request into (api_id, stage, execute_path).

    Supports three addressing modes, in priority order:
      1. Host-based (AWS-native):   {apiId}.execute-api.<host>[:port]/{stage}/{path}
      2. LocalStack-compat (new):   <host>[:port]/_aws/execute-api/{apiId}/{stage}/{path}
      3. LocalStack-compat (v1):    <host>[:port]/restapis/{apiId}/{stage}/_user_request_/{path}

    The path-based forms exist because (a) browsers on macOS don't resolve
    `*.localhost` and (b) many HTTP clients can't override the `Host` header
    (issue #401). Returns ``None`` if none of the three patterns match."""
    m = _EXECUTE_API_RE.match(host)
    if m:
        api_id = m.group(1)
        parts = path.lstrip("/").split("/", 1)
        stage = parts[0] if parts and parts[0] else "$default"
        execute_path = "/" + parts[1] if len(parts) > 1 else "/"
        return api_id, stage, execute_path

    # LocalStack-compat: /_aws/execute-api/{apiId}/{stage}/{path...}
    if path.startswith("/_aws/execute-api/"):
        rest = path[len("/_aws/execute-api/") :]
        parts = rest.split("/", 2)
        if len(parts) >= 2 and parts[0]:
            api_id = parts[0]
            stage = parts[1] if parts[1] else "$default"
            execute_path = "/" + parts[2] if len(parts) > 2 else "/"
            return api_id, stage, execute_path

    # LocalStack v1 legacy: /restapis/{apiId}/{stage}/_user_request_/{path...}
    if path.startswith("/restapis/"):
        rest = path[len("/restapis/") :]
        parts = rest.split("/", 3)
        if len(parts) >= 3 and parts[2] == "_user_request_":
            api_id = parts[0]
            stage = parts[1] if parts[1] else "$default"
            execute_path = "/" + parts[3] if len(parts) > 3 else "/"
            return api_id, stage, execute_path

    return None


def _resolve_stage_and_path(api_id: str, tentative_stage: str, execute_path: str) -> tuple[str, str]:
    """Pick (stage, execute_path) based on the API's configured stages.

    AWS v2 HTTP / WebSocket APIs configured with the ``$default`` stage serve
    from the root of the execute-api URL — no stage segment in the path. v1
    REST APIs always carry the stage as the first path segment. We can't tell
    from the URL alone which pattern applies, so we check the API's configured
    stages and route accordingly (issue #404).

    Rules:
      - If the tentative first segment IS a configured stage name, strip it.
      - Else if the API has a ``$default`` stage, use that and treat the
        whole original path (including ``tentative_stage``) as ``execute_path``.
      - Else fall through (``handle_execute`` will return "Stage not found").
    """
    apigw_v1 = _get_module("apigateway_v1")
    if api_id in apigw_v1._rest_apis:
        stages_map = apigw_v1._stages_v1.get(api_id, {})
    else:
        stages_map = _get_module("apigateway")._stages.get(api_id, {})

    if tentative_stage in stages_map:
        return tentative_stage, execute_path
    if "$default" in stages_map:
        if execute_path == "/":
            resolved_path = "/" + tentative_stage if tentative_stage else "/"
        else:
            resolved_path = "/" + tentative_stage + execute_path
        return "$default", resolved_path
    # No match — let handle_execute report the stage miss verbatim.
    return tentative_stage, execute_path


async def _handle_execute_api_request(
    host: str, path: str, method: str, headers: dict, body: bytes, query_params: dict
):
    """Handle API Gateway execute-api data plane requests (Host-based + path-based)."""
    parsed = _parse_execute_api_url(host, path)
    if parsed is None:
        return None
    api_id, tentative_stage, execute_path = parsed
    try:
        # WebSocket @connections management API — /{stage}/@connections/{id}.
        # The @connections prefix is authoritative; skip $default resolution.
        if execute_path.startswith("/@connections/"):
            connection_id = execute_path[len("/@connections/") :].split("/", 1)[0]
            return await _get_module("apigateway").handle_connections_api(
                method, api_id, tentative_stage, connection_id, body, headers
            )
        stage, execute_path = _resolve_stage_and_path(api_id, tentative_stage, execute_path)
        if api_id in _get_module("apigateway_v1")._rest_apis:
            return await _get_module("apigateway_v1").handle_execute(
                api_id, stage, method, execute_path, headers, body, query_params
            )
        return await _get_module("apigateway").handle_execute(
            api_id, stage, execute_path, method, headers, body, query_params
        )
    except Exception as e:
        logger.exception("Error in execute-api dispatch: %s", e)
        return 500, {"Content-Type": "application/json"}, json.dumps({"message": str(e)}).encode()


def _is_potential_alb_request(host: str, path: str) -> bool:
    """Cheap ALB gate so ordinary requests avoid loading the ALB module."""
    hostname = host.split(":")[0].lower()
    return (
        path.startswith(_ALB_PATH_PREFIX)
        or hostname.endswith(".elb.amazonaws.com")
        or hostname.endswith(".alb.localhost")
    )


async def _handle_alb_request(host: str, path: str, method: str, headers: dict, body: bytes, query_params: dict):
    """Handle ALB data-plane requests for host-based and /_alb-prefixed addressing."""
    if not _is_potential_alb_request(host, path):
        return None

    alb_module = _get_module("alb")
    load_balancer = alb_module.find_lb_for_host(host)
    dispatch_path = path

    if load_balancer is None and path.startswith(_ALB_PATH_PREFIX):
        path_parts = path[len(_ALB_PATH_PREFIX) :].split("/", 1)
        load_balancer = alb_module._find_lb_by_name(path_parts[0])
        if load_balancer:
            dispatch_path = "/" + path_parts[1] if len(path_parts) > 1 else "/"

    if load_balancer is None:
        return None

    alb_port = 80
    if ":" in host:
        try:
            alb_port = int(host.rsplit(":", 1)[-1])
        except ValueError:
            pass

    try:
        return await alb_module.dispatch_request(
            load_balancer, method, dispatch_path, headers, body, query_params, alb_port
        )
    except Exception as e:
        logger.exception("Error in ALB data-plane dispatch: %s", e)
        return 500, {"Content-Type": "application/json"}, json.dumps({"message": str(e)}).encode()


async def _handle_s3_vhost_request(host: str, path: str, method: str, headers: dict, body: bytes, query_params: dict):
    """Handle virtual-hosted S3 requests before generic routing."""
    bucket = _extract_s3_vhost_bucket(host)
    if not bucket or _S3_VHOST_EXCLUDE_RE.search(host) or bucket in _NON_S3_VHOST_NAMES:
        return None
    # CloudFront KVS data-plane clients (boto3 cloudfront-keyvaluestore with
    # inject_host_prefix=False) hit kumostack with host=localhost and path
    # prefixed by /key-value-stores/. Host-name exclusion above doesn't fire,
    # so guard explicitly here too.
    if path.startswith("/key-value-stores/"):
        return None
    # MWAA REST endpoints (api.airflow.{region}, env.airflow.{region}) — boto3
    # expands the model's hostPrefix even when endpoint_url is overridden, so
    # the host arrives as `api.localhost:4566`, and `api` looks like an S3
    # bucket. Short-circuit any path that matches a real MWAA operation:
    #   /environments, /environments/{Name}, /webtoken/{Name},
    #   /clitoken/{Name}, /restapi/{Name}, /metrics/environments/{Name}
    if (
        path == "/environments"
        or path.startswith("/environments/")
        or path.startswith("/webtoken/")
        or path.startswith("/clitoken/")
        or path.startswith("/restapi/")
        or path.startswith("/metrics/environments/")
    ):
        return None

    vhost_path = "/" + bucket + path if path != "/" else "/" + bucket + "/"
    try:
        return await _get_module("s3").handle_request(method, vhost_path, headers, body, query_params)
    except Exception as e:
        logger.exception("Error handling virtual-hosted S3 request: %s", e)
        from xml.sax.saxutils import escape as _xml_esc

        return (
            500,
            {"Content-Type": "application/xml"},
            (f"<Error><Code>InternalError</Code><Message>{_xml_esc(str(e))}</Message></Error>".encode()),
        )


def _with_data_plane_headers(response, request_id: str, include_s3_id: bool = False, wildcard_cors: bool = True):
    """Attach common data-plane request-id headers to a response tuple.

    ``wildcard_cors`` controls whether a wildcard ``Access-Control-Allow-Origin: *``
    is added. API Gateway owns its own CORS (per-API ``corsConfiguration``,
    issue #406) so the caller passes ``wildcard_cors=False`` there to avoid
    clobbering the per-config value. Respects any ``Access-Control-Allow-Origin``
    already set by the upstream handler."""
    if response is None:
        return None
    status, headers, body = response
    if wildcard_cors and "Access-Control-Allow-Origin" not in headers:
        headers["Access-Control-Allow-Origin"] = "*"
    headers["x-amzn-requestid"] = request_id
    headers["x-amz-request-id"] = request_id
    if include_s3_id:
        headers["x-amz-id-2"] = base64.b64encode(os.urandom(48)).decode()
    return status, headers, body


async def _handle_special_data_plane_request(
    method: str,
    path: str,
    headers: dict,
    body: bytes,
    query_params: dict,
    request_id: str,
):
    """Handle special-case service entrypoints before the generic router."""
    if response := await _handle_s3_control_request(path, method, body, query_params, request_id):
        return response
    if response := await _handle_rds_data_request(method, path, headers, body, query_params):
        return response
    if response := await _handle_ses_v2_request(method, path, headers, body, query_params):
        return response
    if response := await _handle_ecr_registry_request(method, path, headers, body, query_params):
        return _with_data_plane_headers(response, request_id)

    host = headers.get("host", "")
    if response := await _handle_execute_api_request(host, path, method, headers, body, query_params):
        return _with_data_plane_headers(response, request_id, wildcard_cors=False)
    if response := await _handle_s3_vhost_request(host, path, method, headers, body, query_params):
        return _with_data_plane_headers(response, request_id, include_s3_id=True)
    if response := await _handle_alb_request(host, path, method, headers, body, query_params):
        return _with_data_plane_headers(response, request_id)
    return None


# ---------------------------------------------------------------------------
# CloudTrail event recording helpers
# ---------------------------------------------------------------------------

_S3_PATH_EVENTS = {
    ("GET", 0): "ListBuckets",
    ("PUT", 1): "CreateBucket",
    ("DELETE", 1): "DeleteBucket",
    ("HEAD", 1): "HeadBucket",
    ("GET", 1): "ListObjects",
    ("PUT", 2): "PutObject",
    ("GET", 2): "GetObject",
    ("DELETE", 2): "DeleteObject",
    ("HEAD", 2): "HeadObject",
    ("POST", 2): "CreateMultipartUpload",
}


def _ct_event_name(service: str, method: str, path: str, headers: dict, query_params: dict) -> str:
    target = headers.get("x-amz-target", "")
    if target and "." in target:
        return target.rsplit(".", 1)[-1]

    action = query_params.get("Action", "")
    if isinstance(action, list):
        action = action[0] if action else ""
    if action:
        return action

    if service == "s3":
        parts = [p for p in path.split("/") if p]
        depth = min(len(parts), 2)
        return _S3_PATH_EVENTS.get((method, depth), f"{method}.s3")

    if service == "lambda":
        parts = [p for p in path.split("/") if p]
        if "functions" in parts:
            fi = parts.index("functions")
            rest = parts[fi + 1 :]
            if not rest:
                return "CreateFunction" if method == "POST" else "ListFunctions"
            sub = rest[1] if len(rest) > 1 else None
            _sub_map = {
                "invocations": "Invoke",
                "code": "UpdateFunctionCode",
                "configuration": "UpdateFunctionConfiguration",
                "aliases": "CreateAlias" if method == "POST" else "ListAliases",
                "versions": "PublishVersion" if method == "POST" else "ListVersionsByFunction",
            }
            if sub in _sub_map:
                return _sub_map[sub]
            return {"GET": "GetFunction", "DELETE": "DeleteFunction", "PUT": "UpdateFunctionCode"}.get(
                method, f"{method}.lambda"
            )

    return f"{method}.{service}"


def _ct_resources(service: str, method: str, path: str, body: bytes) -> list:
    if service == "s3":
        parts = [p for p in path.split("/") if p]
        if not parts:
            return []
        resources = [{"ResourceName": parts[0], "ResourceType": "AWS::S3::Bucket"}]
        if len(parts) >= 2:
            resources.append(
                {"ResourceName": "/".join(parts[1:]), "ResourceType": "AWS::S3::Object"}
            )
        return resources

    if service in ("dynamodb", "lambda", "sqs", "sns", "kinesis"):
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {}

        if service == "dynamodb":
            table = parsed.get("TableName", "")
            if table:
                return [{"ResourceName": table, "ResourceType": "AWS::DynamoDB::Table"}]

        if service == "lambda":
            fn = parsed.get("FunctionName", "")
            if not fn:
                parts = [p for p in path.split("/") if p]
                if "functions" in parts:
                    fi = parts.index("functions")
                    rest = parts[fi + 1 :]
                    fn = rest[0] if rest else ""
            if fn:
                return [{"ResourceName": fn, "ResourceType": "AWS::Lambda::Function"}]

        if service == "sqs":
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2:
                return [{"ResourceName": parts[-1], "ResourceType": "AWS::SQS::Queue"}]

        if service == "sns":
            topic = parsed.get("TopicArn", "")
            if topic:
                return [{"ResourceName": topic, "ResourceType": "AWS::SNS::Topic"}]

        if service == "kinesis":
            stream = parsed.get("StreamName", "")
            if stream:
                return [{"ResourceName": stream, "ResourceType": "AWS::Kinesis::Stream"}]

    return []


def _ct_request_params(headers: dict, body: bytes, query_params: dict) -> dict:
    ct = headers.get("content-type", "")
    if "json" in ct:
        try:
            return json.loads(body) if body else {}
        except Exception:
            return {}
    if "form" in ct:
        try:
            from urllib.parse import parse_qs as _pqs
            raw = {k: v[0] if len(v) == 1 else v for k, v in _pqs(body.decode("utf-8", errors="replace")).items()}
            return raw
        except Exception:
            return {}
    return {}


def _maybe_record_cloudtrail(
    service: str,
    method: str,
    path: str,
    headers: dict,
    body: bytes,
    query_params: dict,
    request_id: str,
    region: str,
):
    """Best-effort CloudTrail event recording.

    Zero hot-path cost when CLOUDTRAIL_RECORDING is not set: the cloudtrail
    module is never loaded and the dict lookup short-circuits immediately.
    When CLOUDTRAIL_RECORDING=1 is set, the module is loaded on the first
    request so recording begins from the very first API call, not just after
    someone has explicitly called a CloudTrail endpoint.
    """
    if service == "cloudtrail" or path.startswith("/_"):
        return
    ct_mod = _loaded_modules.get("cloudtrail")
    if ct_mod is None:
        # Only pay the import cost if CLOUDTRAIL_RECORDING is explicitly on.
        # This keeps the default-off hot path to a single O(1) dict lookup.
        if os.environ.get("CLOUDTRAIL_RECORDING", "0") != "1":
            return
        ct_mod = _get_module("cloudtrail")
    if isinstance(ct_mod, _ErrorModule):
        return
    if not getattr(ct_mod, "_recording_enabled", False):
        return
    try:
        event_name = _ct_event_name(service, method, path, headers, query_params)
        resources = _ct_resources(service, method, path, body)
        access_key_id = extract_access_key_id(headers) or "test"
        user_agent = headers.get("user-agent", "")
        request_params = _ct_request_params(headers, body, query_params)
        ct_mod.record_event(
            service=service,
            event_name=event_name,
            username=access_key_id,
            access_key_id=access_key_id,
            resources=resources,
            region=region,
            request_id=request_id,
            user_agent=user_agent,
            request_params=request_params,
            method=method,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tier 4 — Generic service dispatch
# ---------------------------------------------------------------------------


def _routing_params(method: str, path: str, headers: dict, body: bytes, query_params: dict) -> dict:
    """Augment routing params for unsigned form-encoded requests whose Action lives in the body."""
    routing_params = query_params
    if not query_params.get("Action") and headers.get("content-type", "").startswith(
        "application/x-www-form-urlencoded"
    ):
        body_params = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        if body_params.get("Action"):
            routing_params = {**query_params, "Action": body_params["Action"]}
    return routing_params


async def _dispatch_service_request(
    method: str, path: str, headers: dict, body: bytes, query_params: dict, request_id: str
):
    """Dispatch a request through the generic service router."""
    _t_start = _time.monotonic()
    routing_params = _routing_params(method, path, headers, body, query_params)
    service = detect_service(method, path, headers, routing_params)
    region = extract_region(headers)

    logger.debug("%s %s -> service=%s region=%s", method, path, service, region)

    handler = SERVICE_HANDLERS.get(service)
    if not handler:
        return (
            400,
            {"Content-Type": "application/json"},
            json.dumps({"error": f"Unsupported service: {service}"}).encode(),
        )

    # ── Chaos fault injection ───────────────────────────────────────────
    # Extract action from query params or X-Amz-Target header
    _action = (query_params.get("Action", [None])[0]
               or headers.get("x-amz-target", "").split(".")[-1]
               or "*")
    _chaos_fault = await _apply_chaos(service, _action)
    if _chaos_fault is not None:
        _chaos_status, _chaos_hdrs, _chaos_body = _chaos_fault
        _chaos_hdrs.update({"x-amzn-requestid": request_id, "Access-Control-Allow-Origin": "*"})
        return _chaos_status, _chaos_hdrs, _chaos_body
    # ── End chaos ──────────────────────────────────────────────────────

    try:
        status, resp_headers, resp_body = await handler(method, path, headers, body, query_params)
    except Exception as e:
        logger.exception("Error handling %s request: %s", service, e)
        return (
            500,
            {"Content-Type": "application/json"},
            json.dumps({"__type": "InternalError", "message": str(e)}).encode(),
        )

    _maybe_record_cloudtrail(service, method, path, headers, body, query_params, request_id, region)

    # ── Append to request trace log ────────────────────────────────────
    _t_end = _time.monotonic()
    with _request_log_lock:
        _request_log.append({
            "id":          request_id,
            "method":      method,
            "service":     service,
            "action":      _action,
            "path":        path,
            "status":      status,
            "duration_ms": round((_t_end - _t_start) * 1000) if "_t_start" in dir() else 0,
            "timestamp":   _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "region":      region,
        })
    # ── End request log ────────────────────────────────────────────────

    resp_headers.update(
        {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*",
            "x-amzn-requestid": request_id,
            "x-amz-request-id": request_id,
            "x-amz-id-2": base64.b64encode(os.urandom(48)).decode(),
        }
    )
    return status, resp_headers, resp_body


# ---------------------------------------------------------------------------
# Chaos Engineering — fault injection store + middleware
# ---------------------------------------------------------------------------

import random
import threading
import time as _time
from collections import deque

_chaos_lock = threading.Lock()
_chaos_rules: dict[str, dict] = {}  # rule_id → rule

# Session start time used by the cost estimation engine
_COST_START_TIME: float = _time.time()

# ── Request trace log ────────────────────────────────────────────────────────
_request_log: deque = deque(maxlen=500)  # ring buffer of recent API calls
_request_log_lock = threading.Lock()

# Region health: region → "healthy" | "degraded" | "down"
_region_health: dict[str, str] = {}

# Lambda failure injection: function_name → config
_lambda_failure: dict[str, dict] = {}

# Pumba job tracking: job_id → {container, type, status, started_at}
_pumba_jobs: dict[str, dict] = {}


def _chaos_rule_id() -> str:
    return uuid.uuid4().hex[:8]


def _chaos_rule_expired(rule: dict) -> bool:
    exp = rule.get("expires_at")
    return bool(exp and _time.time() > exp)


def _chaos_active_rules() -> list[dict]:
    now = _time.time()
    with _chaos_lock:
        return [
            r for r in _chaos_rules.values()
            if r["status"] == "active" and (not r.get("expires_at") or r["expires_at"] > now)
        ]


def _chaos_match(rule: dict, service: str, action: str) -> bool:
    rs = rule.get("target_service", "*")
    ra = rule.get("target_action", "*")
    rr = rule.get("target_region", "*")
    if rs not in ("*", service) or ra not in ("*", action):
        return False
    if rr != "*":
        try:
            from kumostack.core.responses import get_region
            if get_region() != rr:
                return False
        except Exception:
            pass
    return True


async def _apply_chaos(service: str, action: str):
    """Check active chaos rules and optionally raise a fault response tuple.

    Returns a (status, headers, body) tuple if a fault fires, else None.
    """
    # ── Region-level health check ─────────────────────────────────────
    try:
        from kumostack.core.responses import get_region
        current_region = get_region()
    except Exception:
        current_region = "us-east-1"

    region_status = _region_health.get(current_region, "healthy")
    headers = {"Content-Type": "application/json"}

    if region_status == "down":
        return (
            503, headers,
            json.dumps({
                "__type": "ServiceUnavailableException",
                "message": f"Region {current_region} is simulated as DOWN (chaos region outage)",
            }).encode(),
        )
    if region_status == "degraded":
        await asyncio.sleep(random.uniform(1.0, 3.0))  # inject latency for degraded region

    for rule in _chaos_active_rules():
        if not _chaos_match(rule, service, action):
            continue
        if random.random() > rule.get("fault_rate", 1.0):
            continue

        # Record trigger
        with _chaos_lock:
            if rule["id"] in _chaos_rules:
                _chaos_rules[rule["id"]]["trigger_count"] += 1
                _chaos_rules[rule["id"]]["last_triggered"] = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())

        ft = rule.get("fault_type", "error")
        headers = {"Content-Type": "application/json"}

        if ft == "latency":
            await asyncio.sleep(rule.get("delay_ms", 1000) / 1000)
            return None  # latency-only, let request proceed

        if ft == "throttle":
            return (
                400, headers,
                json.dumps({
                    "__type": "ThrottlingException",
                    "message": f"Rate exceeded — chaos rule '{rule['id']}' is active",
                }).encode(),
            )

        if ft == "unavailable":
            return (
                503, headers,
                json.dumps({
                    "__type": "ServiceUnavailableException",
                    "message": f"Service unavailable — chaos rule '{rule['id']}' is active",
                }).encode(),
            )

        if ft == "timeout":
            await asyncio.sleep(30)  # force a client timeout
            return (504, headers, json.dumps({"__type": "GatewayTimeout"}).encode())

        # default: generic error
        return (
            500, headers,
            json.dumps({
                "__type": "InternalError",
                "message": f"Injected error — chaos rule '{rule['id']}' is active",
            }).encode(),
        )
    return None


async def _handle_chaos_request(method: str, path: str, body: bytes, query_params: dict):
    """Handle /_kumostack/chaos/* requests."""
    if not path.startswith("/_kumostack/chaos"):
        return None
    ct = {"Content-Type": "application/json"}

    # GET /_kumostack/chaos  — list all rules
    if method == "GET" and path == "/_kumostack/chaos":
        with _chaos_lock:
            rules = list(_chaos_rules.values())
        return 200, ct, json.dumps({"rules": rules}).encode()

    # POST /_kumostack/chaos  — create rule
    # Skip if body is empty (pre-body routing pass); real body arrives in the data-plane pass.
    if method == "POST" and path == "/_kumostack/chaos":
        if not body:
            return None
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, ct, json.dumps({"error": "invalid JSON"}).encode()

        now = _time.time()
        duration = int(data.get("duration_seconds", 0))
        rule = {
            "id":             data.get("id") or _chaos_rule_id(),
            "name":           data.get("name", "Untitled experiment"),
            "target_service": data.get("target_service", "*"),
            "target_action":  data.get("target_action", "*"),
            "fault_type":     data.get("fault_type", "error"),
            "fault_rate":     float(data.get("fault_rate", 1.0)),
            "delay_ms":       int(data.get("delay_ms", 1000)),
            "status":         "active",
            "created_at":     _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "expires_at":     now + duration if duration > 0 else None,
            "duration_seconds": duration,
            "trigger_count":  0,
            "last_triggered": None,
        }
        with _chaos_lock:
            _chaos_rules[rule["id"]] = rule
        logger.info("Chaos rule created: %s (%s → %s fault_type=%s rate=%.0f%%)",
                    rule["id"], rule["target_service"], rule["target_action"],
                    rule["fault_type"], rule["fault_rate"] * 100)
        return 200, ct, json.dumps(rule).encode()

    # DELETE /_kumostack/chaos/<id>  — stop/remove rule
    if method == "DELETE" and path.startswith("/_kumostack/chaos/"):
        rule_id = path.split("/")[-1]
        with _chaos_lock:
            removed = _chaos_rules.pop(rule_id, None)
        if not removed:
            return 404, ct, json.dumps({"error": "rule not found"}).encode()
        logger.info("Chaos rule removed: %s", rule_id)
        return 200, ct, json.dumps({"deleted": rule_id}).encode()

    # PATCH /_kumostack/chaos/<id>  — update status (stop/resume)
    if method == "PATCH" and path.startswith("/_kumostack/chaos/"):
        rule_id = path.split("/")[-1]
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, ct, json.dumps({"error": "invalid JSON"}).encode()
        with _chaos_lock:
            if rule_id not in _chaos_rules:
                return 404, ct, json.dumps({"error": "rule not found"}).encode()
            if "status" in data:
                _chaos_rules[rule_id]["status"] = data["status"]
            updated = dict(_chaos_rules[rule_id])
        return 200, ct, json.dumps(updated).encode()

    # DELETE /_kumostack/chaos  — clear all rules
    if method == "DELETE" and path == "/_kumostack/chaos":
        with _chaos_lock:
            count = len(_chaos_rules)
            _chaos_rules.clear()
        return 200, ct, json.dumps({"cleared": count}).encode()

    return None


# ---------------------------------------------------------------------------
# Chaos — Pumba, region outage, failure-lambda, container list
# ---------------------------------------------------------------------------

def _get_docker_client():
    """Lazy-load Docker client (reuse pattern from elasticache/rds)."""
    try:
        import docker as _docker_pkg
        return _docker_pkg.from_env()
    except Exception:
        return None


async def _handle_chaos_pumba(method: str, path: str, body: bytes):
    """POST /_kumostack/chaos/pumba — run Pumba network/stress chaos on a container."""
    if method != "POST" or path != "/_kumostack/chaos/pumba":
        return None
    if not body:
        return None
    ct = {"Content-Type": "application/json"}
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return 400, ct, json.dumps({"error": "invalid JSON"}).encode()

    container = data.get("container")
    chaos_type = data.get("chaos_type", "network_delay")
    duration   = int(data.get("duration_seconds", 30))
    delay_ms   = int(data.get("delay_ms", 100))
    loss_pct   = float(data.get("loss_percent", 10))
    corrupt_pct= float(data.get("corrupt_percent", 5))
    cpus       = int(data.get("cpus", 1))

    if not container:
        return 400, ct, json.dumps({"error": "container name required"}).encode()

    dc = _get_docker_client()
    if not dc:
        return 503, ct, json.dumps({"error": "Docker not available"}).encode()

    type_to_cmd = {
        "network_delay":    f"netem --duration {duration}s --delay {delay_ms}ms delay {container}",
        "network_loss":     f"netem --duration {duration}s --loss {loss_pct} loss {container}",
        "network_corrupt":  f"netem --duration {duration}s --corrupt {corrupt_pct} corrupt {container}",
        "kill":             f"kill --signal SIGKILL {container}",
        "stress_cpu":       f"stress --duration {duration}s --cpu {cpus} {container}",
    }
    cmd = type_to_cmd.get(chaos_type)
    if not cmd:
        return 400, ct, json.dumps({"error": f"unknown chaos_type: {chaos_type}"}).encode()

    job_id = _chaos_rule_id()
    try:
        dc.containers.run(
            "gaiaadm/pumba:latest",
            command=cmd,
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
            remove=True,
            detach=True,
            name=f"kumostack-pumba-{job_id}",
        )
        with _chaos_lock:
            _pumba_jobs[job_id] = {
                "id": job_id, "container": container, "chaos_type": chaos_type,
                "duration_seconds": duration, "status": "running",
                "started_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            }
        logger.info("Pumba job %s started: %s on %s", job_id, chaos_type, container)
        return 200, ct, json.dumps({"job_id": job_id, "status": "started"}).encode()
    except Exception as e:
        logger.warning("Pumba failed: %s", e)
        return 500, ct, json.dumps({"error": str(e)}).encode()


async def _handle_chaos_containers(method: str, path: str):
    """GET /_kumostack/chaos/containers — list kumostack-managed containers for Pumba targeting."""
    if method != "GET" or path != "/_kumostack/chaos/containers":
        return None
    ct = {"Content-Type": "application/json"}
    dc = _get_docker_client()
    if not dc:
        return 200, ct, json.dumps({"containers": []}).encode()
    # Internal KumoStack platform containers — never valid Pumba targets
    _INFRA_NAMES = frozenset({
        "kumostack", "kumostack-dashboard", "kumostack-vector", "kumostack-stackport",
        "kumostack-drawio", "kumostack-loki", "kumostack-prometheus", "kumostack-grafana",
        "kumostack-cadvisor", "kumostack-garage", "kumostack-redis-exporter",
        "ministack-dashboard", "ministack-vector", "ministack-loki", "ministack-prometheus",
        "ministack-grafana", "ministack-cadvisor",
    })
    try:
        # Primary: containers labeled with kumostack service labels (RDS, ElastiCache, OpenSearch, ECS, EKS…)
        service_containers: list[dict] = []
        seen_ids: set[str] = set()

        for label_filter in ("kumostack=rds", "kumostack=elasticache", "kumostack=ecs",
                             "kumostack=eks", "kumostack=lambda",
                             "com.kumostack.service"):
            for c in dc.containers.list(filters={"label": label_filter}):
                if c.short_id in seen_ids:
                    continue
                seen_ids.add(c.short_id)
                svc_type = (
                    c.labels.get("kumostack") or
                    c.labels.get("com.kumostack.service") or
                    "aws"
                )
                service_containers.append({
                    "name":     c.name,
                    "id":       c.short_id,
                    "status":   c.status,
                    "labels":   dict(c.labels),
                    "image":    c.image.tags[0] if c.image.tags else "unknown",
                    "svc_type": svc_type,
                })

        return 200, ct, json.dumps({"containers": service_containers}).encode()
    except Exception as e:
        return 500, ct, json.dumps({"error": str(e)}).encode()


async def _handle_chaos_region(method: str, path: str, body: bytes):
    """GET/POST /_kumostack/chaos/region — manage region health state."""
    if not path.startswith("/_kumostack/chaos/region"):
        return None
    ct = {"Content-Type": "application/json"}

    if method == "GET":
        with _chaos_lock:
            state = dict(_region_health)
        return 200, ct, json.dumps({"regions": state}).encode()

    if method == "POST":
        if not body:
            return None
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, ct, json.dumps({"error": "invalid JSON"}).encode()
        region = data.get("region")
        status = data.get("status", "down")  # "healthy" | "degraded" | "down"
        if not region:
            return 400, ct, json.dumps({"error": "region required"}).encode()
        with _chaos_lock:
            if status == "healthy":
                _region_health.pop(region, None)
            else:
                _region_health[region] = status
        logger.info("Region %s marked as %s (chaos)", region, status)
        return 200, ct, json.dumps({"region": region, "status": status}).encode()

    if method == "DELETE":
        with _chaos_lock:
            _region_health.clear()
        return 200, ct, json.dumps({"cleared": True}).encode()

    return None


async def _handle_chaos_lambda_failure(method: str, path: str, body: bytes):
    """GET/POST/DELETE /_kumostack/chaos/lambda-failure — failure-lambda style injection."""
    if not path.startswith("/_kumostack/chaos/lambda-failure"):
        return None
    ct = {"Content-Type": "application/json"}

    if method == "GET":
        with _chaos_lock:
            return 200, ct, json.dumps({"failures": list(_lambda_failure.values())}).encode()

    if method == "POST":
        if not body:
            return None
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, ct, json.dumps({"error": "invalid JSON"}).encode()

        fn = data.get("function_name", "*")
        config = {
            "function_name":   fn,
            "failure_mode":    data.get("failure_mode", "exception"),  # exception | statuscode | blacklist | latency
            "exception_msg":   data.get("exception_msg", "Simulated failure — chaos"),
            "rate":            float(data.get("rate", 1.0)),
            "status_code":     int(data.get("status_code", 500)),
            "latency_ms":      int(data.get("latency_ms", 3000)),
            "blacklist":       data.get("blacklist", []),
            "created_at":      _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        with _chaos_lock:
            _lambda_failure[fn] = config
        logger.info("Lambda failure injection set: %s mode=%s rate=%.0f%%", fn, config["failure_mode"], config["rate"]*100)
        return 200, ct, json.dumps(config).encode()

    if method == "DELETE":
        fn = path.split("/")[-1] if path != "/_kumostack/chaos/lambda-failure" else None
        with _chaos_lock:
            if fn and fn in _lambda_failure:
                del _lambda_failure[fn]
            elif not fn:
                _lambda_failure.clear()
        return 200, ct, json.dumps({"ok": True}).encode()

    return None


def get_lambda_failure_config(function_name: str) -> dict | None:
    """Called from lambda_svc to check if a function has failure injection configured."""
    with _chaos_lock:
        return _lambda_failure.get(function_name) or _lambda_failure.get("*")


async def _handle_organizations_api(method: str, path: str, body: bytes):
    """GET /_kumostack/organizations/scps  — list real SCPs for the dashboard.
       POST /_kumostack/organizations/scps — create SCP.
       PATCH /_kumostack/organizations/scps/{id} — toggle status.
       DELETE /_kumostack/organizations/scps/{id} — delete SCP.
    """
    ct = {"Content-Type": "application/json"}
    if not path.startswith("/_kumostack/organizations"):
        return None

    # PATCH and POST require a body — skip in the pre-body routing pass (body not yet read)
    # DELETE has no body so always allow it through
    if method in ("PATCH", "POST") and not body:
        return None

    from kumostack.services import organizations as _org
    from kumostack.core.responses import get_account_id

    def _mgmt_check():
        """Return error tuple if caller is not the management account."""
        org = _org._orgs.get("self")
        if org and org.get("MasterAccountId"):
            caller = get_account_id()
            if org["MasterAccountId"] != caller:
                return (403, ct, json.dumps({
                    "error": "AccessDeniedException",
                    "message": f"Service Control Policies can only be managed from the management account ({org['MasterAccountId']}). Current account: {caller}",
                }).encode())
        return None

    if path == "/_kumostack/organizations/scps":
        if method == "GET":
            return 200, ct, json.dumps({"scps": _org.list_scps_raw()}).encode()
        if method == "POST":
            if err := _mgmt_check(): return err
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                return 400, ct, json.dumps({"error": "invalid JSON"}).encode()
            resp = _org._create_policy({
                "Name":        payload.get("name", "Unnamed"),
                "Description": payload.get("description", ""),
                "Content":     json.dumps(payload.get("content", {"Version": "2012-10-17", "Statement": []})),
                "Type":        "SERVICE_CONTROL_POLICY",
            })
            return resp

    # PATCH /_kumostack/organizations/scps/{id}
    if method == "PATCH" and path.startswith("/_kumostack/organizations/scps/"):
        if err := _mgmt_check(): return err
        policy_id = path.split("/")[-1]
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, ct, json.dumps({"error": "invalid JSON"}).encode()
        if policy_id not in _org._policies:
            return 404, ct, json.dumps({"error": "not found", "id": policy_id}).encode()
        if "status" in payload:
            _org.set_scp_status(policy_id, payload["status"])
        if "attachedTo" in payload:
            _org.set_scp_attachments(policy_id, payload["attachedTo"])
        return 200, ct, json.dumps({"ok": True, "policy": policy_id}).encode()

    # DELETE /_kumostack/organizations/scps/{id}
    if method == "DELETE" and path.startswith("/_kumostack/organizations/scps/"):
        if err := _mgmt_check(): return err
        policy_id = path.split("/")[-1]
        _org._policies.pop(policy_id, None)
        return 200, ct, json.dumps({"deleted": policy_id}).encode()

    return None


async def _handle_sts_log_api(method: str, path: str):
    """GET /_kumostack/sts/assume-role-log — return AssumeRole audit log."""
    if path != "/_kumostack/sts/assume-role-log" or method != "GET":
        return None
    from kumostack.services.sts import get_assume_role_log
    ct = {"Content-Type": "application/json"}
    return 200, ct, json.dumps({"log": get_assume_role_log()}).encode()


async def _handle_cloudtrail_api(method: str, path: str, query_params: dict):
    """GET /_kumostack/cloudtrail/events — return recent CloudTrail events for the dashboard."""
    if path != "/_kumostack/cloudtrail/events" or method != "GET":
        return None
    ct_mod = _loaded_modules.get("cloudtrail") or _get_module("cloudtrail")
    if not ct_mod or isinstance(ct_mod, _ErrorModule):
        return 200, {"Content-Type": "application/json"}, json.dumps({"events": []}).encode()
    q = ct_mod._get_event_queue()
    events = list(reversed(list(q)))
    # Optional filters: service, event_name, limit
    service_filter = query_params.get("service", [None])[0]
    name_filter = query_params.get("event_name", [None])[0]
    try:
        limit = int(query_params.get("limit", [200])[0])
    except (TypeError, ValueError):
        limit = 200
    if service_filter:
        svc_src = f"{service_filter}.amazonaws.com"
        events = [e for e in events if e.get("EventSource") == svc_src]
    if name_filter:
        events = [e for e in events if e.get("EventName") == name_filter]
    return 200, {"Content-Type": "application/json"}, json.dumps({"events": events[:limit]}).encode()


async def _handle_cost_report(method: str, path: str):
    """GET /_kumostack/cost/report — estimate AWS costs from CloudTrail events + resource counts."""
    if method != "GET" or path != "/_kumostack/cost/report":
        return None
    ct = {"Content-Type": "application/json"}

    uptime_hours = max((_time.time() - _COST_START_TIME) / 3600, 1 / 3600)

    # ── Collect API call counts from CloudTrail ──────────────────────────────
    svc_actions: dict[str, dict[str, int]] = {}
    ct_mod = _loaded_modules.get("cloudtrail")
    if ct_mod:
        try:
            queue = ct_mod._events.get("events") or []
            for ev in queue:
                svc    = ev.get("EventSource", "").replace(".amazonaws.com", "").lower()
                action = ev.get("EventName", "")
                if svc and action:
                    svc_actions.setdefault(svc, {})[action] = svc_actions.get(svc, {}).get(action, 0) + 1
        except Exception:
            pass

    # ── Collect live resource counts ─────────────────────────────────────────
    def _count(mod_name: str, attr: str) -> int:
        mod = _loaded_modules.get(mod_name)
        if not mod:
            return 0
        try:
            return len(list(getattr(mod, attr).values()))
        except Exception:
            return 0

    resource_counts = {
        "lambda_functions": _count("lambda_svc", "_functions"),
        "dynamodb_tables":  _count("dynamodb",   "_tables"),
        "s3_buckets":       _count("s3",          "_buckets"),
        "sqs_queues":       _count("sqs",         "_queues"),
        "sns_topics":       _count("sns",         "_topics"),
        "rds_instances":    _count("rds",         "_instances"),
        "state_machines":   _count("stepfunctions", "_state_machines"),
        "secrets":          _count("secretsmanager", "_secrets"),
    }

    # ── AWS pricing constants (us-east-1 on-demand) ──────────────────────────
    PRICES = {
        # Lambda: $0.20/1M requests + $0.0000166667/GB-s (128 MB, 200 ms avg)
        "lambda_invoke":         0.0000002 + 0.0000004267,   # /invocation
        # DynamoDB
        "dynamo_write":          0.00000125,   # per WCU ($1.25/1M)
        "dynamo_read":           0.00000025,   # per RCU ($0.25/1M)
        # S3
        "s3_put":                0.000005,     # per PUT/COPY/POST/LIST ($0.005/1K)
        "s3_get":                0.0000004,    # per GET/HEAD ($0.0004/1K)
        # SQS
        "sqs_api":               0.0000004,    # per API call ($0.40/1M)
        # SNS
        "sns_publish":           0.0000005,    # per notification ($0.50/1M)
        # CloudWatch
        "cw_api":                0.00001,      # per 1K API calls ($0.01/1K)
        # Secrets Manager: $0.05/10K API calls
        "secretsmanager_api":    0.000005,
        # KMS: $0.03/10K requests
        "kms_api":               0.000003,
        # EventBridge: $1.00/1M events
        "eventbridge_api":       0.000001,
        # Kinesis: $0.014/shard-hour + $0.04/1M records
        "kinesis_api":           0.00000004,
        # Step Functions: $0.025/1K state transitions
        "stepfunctions_api":     0.000025,
        # ECR: $0.10/GB-month storage + $0.01/GB data transfer (API call proxy)
        "ecr_api":               0.000001,
        # ECS/EKS: per API call proxy cost
        "ecs_api":               0.000001,
        "eks_api":               0.000001,
        # IAM, STS, CloudFormation — free API but count them
        "free_api":              0.0,
    }

    # Per-service monthly resource cost (us-east-1 on-demand, per-resource/month)
    RESOURCE_MONTHLY = {
        "lambda_functions": 0.0,      # charged on invocation, not existence
        "dynamodb_tables":  0.0,      # on-demand billing
        "s3_buckets":       0.023,    # $0.023/GB-month storage; we use $0.023 as floor
        "sqs_queues":       0.0,
        "sns_topics":       0.0,
        "rds_instances":    12.41,    # db.t3.micro on-demand ~$0.017/hr
        "state_machines":   0.0,
        "secrets":          0.40,     # $0.40/secret/month
    }

    def _classify_calls(svc: str, actions: dict[str, int]) -> dict:
        """Map service + actions → cost line items."""
        items: dict[str, tuple[int, float]] = {}  # label → (count, unit_price)

        if svc == "lambda":
            inv = actions.get("Invoke", 0) + actions.get("InvokeFunction", 0)
            items["Invocations"] = (inv, PRICES["lambda_invoke"])

        elif svc in ("dynamodb", "dynamodb2"):
            writes = sum(actions.get(k, 0) for k in ("PutItem","DeleteItem","UpdateItem","BatchWriteItem","TransactWriteItems"))
            reads  = sum(actions.get(k, 0) for k in ("GetItem","Query","Scan","BatchGetItem","TransactGetItems"))
            if writes: items["Write Requests"] = (writes, PRICES["dynamo_write"])
            if reads:  items["Read Requests"]  = (reads,  PRICES["dynamo_read"])

        elif svc == "s3":
            puts = sum(actions.get(k, 0) for k in ("PutObject","CreateBucket","CopyObject","ListObjects","ListObjectsV2","ListBuckets"))
            gets = sum(actions.get(k, 0) for k in ("GetObject","HeadObject","HeadBucket"))
            if puts: items["PUT/LIST Requests"] = (puts, PRICES["s3_put"])
            if gets: items["GET Requests"]      = (gets, PRICES["s3_get"])

        elif svc == "sqs":
            total = sum(actions.values())
            items["API Requests"] = (total, PRICES["sqs_api"])

        elif svc == "sns":
            total = sum(actions.values())
            items["Notifications"] = (total, PRICES["sns_publish"])

        elif svc in ("monitoring", "cloudwatch", "logs"):
            total = sum(actions.values())
            items["API Requests"] = (total, PRICES["cw_api"])

        elif svc == "secretsmanager":
            total = sum(actions.values())
            items["API Calls"] = (total, PRICES["secretsmanager_api"])

        elif svc == "kms":
            total = sum(actions.values())
            items["Cryptographic Ops"] = (total, PRICES["kms_api"])

        elif svc == "events":
            total = sum(actions.values())
            items["Events"] = (total, PRICES["eventbridge_api"])

        elif svc == "kinesis":
            total = sum(actions.values())
            items["Data Records"] = (total, PRICES["kinesis_api"])

        elif svc == "states":
            total = sum(actions.values())
            items["State Transitions"] = (total, PRICES["stepfunctions_api"])

        else:
            # IAM, STS, CloudFormation, EC2 control-plane, etc. — free
            total = sum(actions.values())
            items["API Requests"] = (total, PRICES["free_api"])

        return items

    # ── Build line items ──────────────────────────────────────────────────────
    SVC_DISPLAY = {
        "lambda": "Lambda", "dynamodb": "DynamoDB", "s3": "S3",
        "sqs": "SQS", "sns": "SNS", "monitoring": "CloudWatch",
        "logs": "CloudWatch Logs", "secretsmanager": "Secrets Manager",
        "kms": "KMS", "events": "EventBridge", "kinesis": "Kinesis",
        "states": "Step Functions", "iam": "IAM", "sts": "STS",
        "cloudformation": "CloudFormation", "ec2": "EC2",
        "ecs": "ECS", "eks": "EKS", "rds": "RDS", "ecr": "ECR",
        "elasticache": "ElastiCache", "xray": "X-Ray",
    }

    line_items: list[dict] = []
    total_api_calls = 0

    for svc, actions in svc_actions.items():
        svc_total_calls = sum(actions.values())
        total_api_calls += svc_total_calls
        classified = _classify_calls(svc, actions)
        svc_cost = sum(count * price for _, (count, price) in classified.items())

        line_items.append({
            "service":        SVC_DISPLAY.get(svc, svc.upper()),
            "service_key":    svc,
            "total_calls":    svc_total_calls,
            "breakdown":      [
                {"label": lbl, "count": cnt, "unit_price": prc, "cost": cnt * prc}
                for lbl, (cnt, prc) in classified.items()
            ],
            "estimated_cost": round(svc_cost, 8),
            "cost_driver":    "api",
        })

    # Resource-hour costs (RDS, Secrets Manager, etc.)
    for res_key, count in resource_counts.items():
        if count == 0:
            continue
        monthly_per = RESOURCE_MONTHLY.get(res_key, 0.0)
        if monthly_per == 0.0:
            continue
        session_cost = count * monthly_per * (uptime_hours / 730)
        svc_label = res_key.replace("_", " ").replace("rds instances", "RDS").replace("secrets", "Secrets Manager").title()
        line_items.append({
            "service":        svc_label,
            "service_key":    res_key,
            "total_calls":    0,
            "breakdown":      [{"label": "Resource Hours", "count": count, "unit_price": monthly_per / 730, "cost": session_cost}],
            "estimated_cost": round(session_cost, 8),
            "cost_driver":    "resource",
        })

    # Sort by cost descending
    line_items.sort(key=lambda x: x["estimated_cost"], reverse=True)

    session_total = sum(i["estimated_cost"] for i in line_items)
    monthly_proj  = (session_total / uptime_hours) * 730 if uptime_hours > 0 else 0

    return 200, ct, json.dumps({
        "uptime_hours":           round(uptime_hours, 4),
        "total_api_calls":        total_api_calls,
        "resource_counts":        resource_counts,
        "estimated_session_cost": round(session_total, 8),
        "monthly_projection":     round(monthly_proj, 4),
        "line_items":             line_items,
        "pricing_region":         "us-east-1",
        "pricing_model":          "on-demand",
    }).encode()


async def _handle_iam_simulate(method: str, path: str, body: bytes):
    """IAM Policy Simulator — /_kumostack/iam/simulate and /_kumostack/iam/principals."""
    if not path.startswith("/_kumostack/iam"):
        return None
    ct = {"Content-Type": "application/json"}

    iam = _loaded_modules.get("iam") or _get_module("iam")

    # ── GET /_kumostack/iam/principals — list all principals ─────────────────
    if method == "GET" and path == "/_kumostack/iam/principals":
        principals = []
        try:
            for name, role in iam._roles.items():
                principals.append({"type": "role", "name": name, "arn": role.get("Arn", "")})
        except Exception:
            pass
        try:
            for name, user in iam._users.items():
                principals.append({"type": "user", "name": name, "arn": user.get("Arn", "")})
        except Exception:
            pass
        return 200, ct, json.dumps({"principals": principals}).encode()

    # ── POST /_kumostack/iam/simulate ────────────────────────────────────────
    if method == "POST" and path == "/_kumostack/iam/simulate":
        data       = json.loads(body or b"{}")
        principal  = data.get("principal", "")    # role name, user name, or full ARN
        actions    = data.get("actions", [])      # list of "service:Action"
        resource   = data.get("resource", "*")
        context    = data.get("context", {})      # optional condition context (future)

        if not principal or not actions:
            return 400, ct, json.dumps({"error": "principal and actions are required"}).encode()

        if isinstance(actions, str):
            actions = [actions]

        # ── Collect all policy documents for the principal ────────────────
        def _resolve_policy_doc(pol_arn_or_doc):
            """Return parsed dict from an ARN or raw document string/dict."""
            if isinstance(pol_arn_or_doc, dict):
                return pol_arn_or_doc
            if isinstance(pol_arn_or_doc, str):
                # Could be a policy ARN or a raw JSON string
                try:
                    return json.loads(pol_arn_or_doc)
                except Exception:
                    pass
            return None

        def _get_managed_doc(arn: str) -> dict | None:
            try:
                rec = iam._policies.get(arn)
                if rec:
                    vid = rec.get("DefaultVersionId", "v1")
                    raw = rec["Versions"][vid]["Document"]
                    return _resolve_policy_doc(raw)
            except Exception:
                pass
            try:
                rec = iam._aws_managed_policies.get(arn)
                if rec:
                    vid = rec.get("DefaultVersionId", "v1")
                    raw = rec["Versions"][vid]["Document"]
                    return _resolve_policy_doc(raw)
            except Exception:
                pass
            return None

        policies_for_eval: list[dict] = []  # each: {name, source, document}

        def _collect_principal_policies(pname: str, ptype: str, pdata: dict):
            # Inline policies
            inline_store = {}
            if ptype == "role":
                inline_store = pdata.get("InlinePolicies", {})
            elif ptype == "user":
                try:
                    inline_store = iam._user_inline_policies.get(pname) or {}
                except Exception:
                    pass

            for pol_name, pol_doc in inline_store.items():
                doc = _resolve_policy_doc(pol_doc)
                if doc:
                    policies_for_eval.append({
                        "name": pol_name, "source": f"Inline on {ptype}/{pname}",
                        "arn": None, "document": doc,
                    })

            # Attached managed policies
            for pol_arn in pdata.get("AttachedPolicies", []):
                doc = _get_managed_doc(pol_arn)
                pol_name = pol_arn.split("/")[-1]
                policies_for_eval.append({
                    "name": pol_name, "source": f"Managed ({pol_arn})",
                    "arn": pol_arn, "document": doc,  # doc may be None if unresolvable
                })

        # Find the principal
        principal_found = False
        try:
            # Try as role name
            role = iam._roles.get(principal)
            if role:
                _collect_principal_policies(principal, "role", role)
                principal_found = True
            else:
                # Try as role ARN — extract name from ARN
                if ":role/" in principal:
                    role_name = principal.split(":role/")[-1].split("/")[-1]
                    role = iam._roles.get(role_name)
                    if role:
                        _collect_principal_policies(role_name, "role", role)
                        principal_found = True
        except Exception:
            pass

        if not principal_found:
            try:
                user = iam._users.get(principal)
                if user:
                    _collect_principal_policies(principal, "user", user)
                    principal_found = True
                elif ":user/" in principal:
                    user_name = principal.split(":user/")[-1]
                    user = iam._users.get(user_name)
                    if user:
                        _collect_principal_policies(user_name, "user", user)
                        principal_found = True
            except Exception:
                pass

        if not principal_found:
            # No IAM entity found — still evaluate with empty policies (implicit deny)
            pass

        # ── IAM evaluation engine ────────────────────────────────────────────

        import fnmatch as _fnmatch

        def _action_matches(pattern: str, action: str) -> bool:
            """Match IAM action pattern (supports * and ? wildcards, case-insensitive)."""
            return _fnmatch.fnmatch(action.lower(), pattern.lower())

        def _resource_matches(pattern: str, res: str) -> bool:
            return _fnmatch.fnmatch(res, pattern)

        def _eval_statement(stmt: dict, action: str, resource: str) -> str | None:
            """Return 'Allow', 'Deny', or None (no match)."""
            effect = stmt.get("Effect", "Allow")

            # Action matching
            actions_field = stmt.get("Action") or stmt.get("NotAction")
            not_action    = "NotAction" in stmt
            if actions_field is None:
                return None
            if isinstance(actions_field, str):
                actions_field = [actions_field]

            action_match = any(_action_matches(a, action) for a in actions_field)
            if not_action:
                action_match = not action_match
            if not action_match:
                return None

            # Resource matching
            resources_field = stmt.get("Resource") or stmt.get("NotResource")
            not_resource    = "NotResource" in stmt
            if resources_field is None:
                return None
            if isinstance(resources_field, str):
                resources_field = [resources_field]

            resource_match = any(_resource_matches(r, resource) for r in resources_field)
            if not_resource:
                resource_match = not resource_match
            if not resource_match:
                return None

            return effect

        results = []
        for action in actions:
            evaluation_steps = []
            decision         = "implicitDeny"
            reason           = "No policy grants access to this action and resource."
            matched_stmt     = None
            matched_policy   = None

            explicit_deny_found = False

            for pol in policies_for_eval:
                doc = pol.get("document")
                if not doc:
                    evaluation_steps.append({
                        "policy": pol["name"], "source": pol["source"],
                        "result": "skip", "reason": "Policy document not resolvable",
                    })
                    continue

                statements = doc.get("Statement", [])
                if isinstance(statements, dict):
                    statements = [statements]

                for i, stmt in enumerate(statements):
                    effect = _eval_statement(stmt, action, resource)
                    sid    = stmt.get("Sid", f"Statement{i+1}")
                    if effect is None:
                        evaluation_steps.append({
                            "policy": pol["name"], "source": pol["source"],
                            "statement": sid, "result": "noMatch",
                            "reason": "Action or Resource did not match",
                        })
                        continue

                    if effect == "Deny":
                        evaluation_steps.append({
                            "policy": pol["name"], "source": pol["source"],
                            "statement": sid, "result": "explicitDeny",
                            "reason": f"Explicit Deny on action '{action}' / resource '{resource}'",
                            "statement_detail": stmt,
                        })
                        explicit_deny_found = True
                        matched_stmt   = stmt
                        matched_policy = pol
                        break
                    elif effect == "Allow" and decision != "allow":
                        decision = "allow"
                        reason   = f"Explicit Allow in statement '{sid}' of policy '{pol['name']}'"
                        matched_stmt   = stmt
                        matched_policy = pol
                        evaluation_steps.append({
                            "policy": pol["name"], "source": pol["source"],
                            "statement": sid, "result": "allow",
                            "reason": f"Allow on action '{action}' / resource '{resource}'",
                            "statement_detail": stmt,
                        })
                    else:
                        evaluation_steps.append({
                            "policy": pol["name"], "source": pol["source"],
                            "statement": sid, "result": "noMatch",
                            "reason": "Action or Resource did not match",
                        })

                if explicit_deny_found:
                    break

            if explicit_deny_found:
                decision = "explicitDeny"
                reason   = f"Explicit Deny in statement '{matched_stmt.get('Sid', '')}' of policy '{matched_policy['name'] if matched_policy else '?'}'"

            results.append({
                "action":           action,
                "resource":         resource,
                "decision":         decision,
                "reason":           reason,
                "policies_checked": len(policies_for_eval),
                "matched_statement": matched_stmt,
                "matched_policy":    matched_policy["name"] if matched_policy else None,
                "matched_source":    matched_policy["source"] if matched_policy else None,
                "evaluation_steps":  evaluation_steps,
            })

        overall = (
            "explicitDeny" if any(r["decision"] == "explicitDeny" for r in results)
            else "allow"   if all(r["decision"] == "allow" for r in results)
            else "implicitDeny"
        )

        return 200, ct, json.dumps({
            "principal":          principal,
            "resource":           resource,
            "overall_decision":   overall,
            "policies_evaluated": len(policies_for_eval),
            "results":            results,
        }).encode()

    return None


async def _handle_topology_request(method: str, path: str):
    """GET /_kumostack/topology — build resource dependency graph from live service state."""
    if method != "GET" or path != "/_kumostack/topology":
        return None
    ct = {"Content-Type": "application/json"}

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()

    def _node(node_id: str, label: str, service: str, arn: str = "") -> dict:
        return {"id": node_id, "label": label, "service": service, "arn": arn}

    def _edge(source: str, target: str, label: str = "") -> dict:
        return {"id": f"{source}→{target}", "source": source, "target": target, "label": label}

    def _add_node(n: dict) -> None:
        if n["id"] not in seen_nodes:
            nodes.append(n)
            seen_nodes.add(n["id"])

    def _add_edge(e: dict) -> None:
        if e["source"] in seen_nodes and e["target"] in seen_nodes:
            edges.append(e)

    try:
        # ── Lambda functions ────────────────────────────────────────────────
        lambda_mod = _loaded_modules.get("lambda_svc")
        if lambda_mod:
            for fn_name, fn in lambda_mod._functions.items():
                nid = f"lambda:{fn_name}"
                _add_node(_node(nid, fn_name, "lambda",
                                fn.get("FunctionArn", f"arn:aws:lambda:us-east-1:000000000000:function:{fn_name}")))

            # Event Source Mappings → Lambda triggers
            for esm_id, esm in lambda_mod._esms.items():
                src_arn = esm.get("EventSourceArn", "")
                fn_arn  = esm.get("FunctionArn",  "")
                fn_name = fn_arn.split(":")[-1] if fn_arn else ""
                fn_nid  = f"lambda:{fn_name}"
                if not fn_name:
                    continue

                if ":sqs:" in src_arn or "sqs" in src_arn.lower():
                    q_name  = src_arn.split(":")[-1]
                    q_nid   = f"sqs:{q_name}"
                    _add_node(_node(q_nid, q_name, "sqs", src_arn))
                    _add_edge(_edge(q_nid, fn_nid, "trigger"))

                elif ":kinesis:" in src_arn:
                    s_name  = src_arn.split("/")[-1]
                    s_nid   = f"kinesis:{s_name}"
                    _add_node(_node(s_nid, s_name, "kinesis", src_arn))
                    _add_edge(_edge(s_nid, fn_nid, "trigger"))

                elif ":dynamodb:" in src_arn and "/stream/" in src_arn:
                    t_name  = src_arn.split("/")[1] if "/" in src_arn else src_arn.split(":")[-1]
                    t_nid   = f"dynamodb:{t_name}"
                    _add_node(_node(t_nid, t_name, "dynamodb", src_arn))
                    _add_edge(_edge(t_nid, fn_nid, "stream"))

    except Exception:
        pass

    try:
        # ── SNS topics + subscriptions ──────────────────────────────────────
        sns_mod = _loaded_modules.get("sns")
        if sns_mod:
            for topic_arn, topic in sns_mod._topics.items():
                t_name = topic_arn.split(":")[-1]
                t_nid  = f"sns:{t_name}"
                _add_node(_node(t_nid, t_name, "sns", topic_arn))

            for sub_arn, sub in sns_mod._sub_arn_to_topic.items():
                topic_arn = sub.get("topic_arn", "")
                t_name    = topic_arn.split(":")[-1]
                t_nid     = f"sns:{t_name}"
                protocol  = sub.get("protocol", "")
                endpoint  = sub.get("endpoint", "")

                if protocol == "lambda":
                    fn_name = endpoint.split(":")[-1]
                    fn_nid  = f"lambda:{fn_name}"
                    _add_node(_node(fn_nid, fn_name, "lambda", endpoint))
                    _add_edge(_edge(t_nid, fn_nid, "subscribe"))

                elif protocol == "sqs":
                    q_name = endpoint.split(":")[-1]
                    q_nid  = f"sqs:{q_name}"
                    _add_node(_node(q_nid, q_name, "sqs", endpoint))
                    _add_edge(_edge(t_nid, q_nid, "subscribe"))

                elif protocol in ("http", "https"):
                    ep_nid = f"http:{endpoint[:40]}"
                    _add_node(_node(ep_nid, endpoint[:30] + "…" if len(endpoint) > 30 else endpoint, "http", endpoint))
                    _add_edge(_edge(t_nid, ep_nid, "subscribe"))

    except Exception:
        pass

    try:
        # ── EventBridge rules + targets ─────────────────────────────────────
        eb_mod = _loaded_modules.get("eventbridge")
        if eb_mod:
            for rule_name, rule in eb_mod._rules.items():
                r_nid = f"eventbridge:{rule_name}"
                _add_node(_node(r_nid, rule_name, "eventbridge",
                                rule.get("Arn", f"arn:aws:events:us-east-1:000000000000:rule/{rule_name}")))

            for rule_name, targets_list in eb_mod._targets.items():
                r_nid   = f"eventbridge:{rule_name}"
                targets = targets_list if isinstance(targets_list, list) else list((targets_list or {}).values())
                for tgt in targets:
                    tgt_arn = tgt.get("Arn", "")
                    if not tgt_arn:
                        continue
                    if ":lambda:" in tgt_arn or "/function:" in tgt_arn:
                        fn_name = tgt_arn.split(":")[-1]
                        fn_nid  = f"lambda:{fn_name}"
                        _add_node(_node(fn_nid, fn_name, "lambda", tgt_arn))
                        _add_edge(_edge(r_nid, fn_nid, "target"))
                    elif ":sqs:" in tgt_arn:
                        q_name = tgt_arn.split(":")[-1]
                        q_nid  = f"sqs:{q_name}"
                        _add_node(_node(q_nid, q_name, "sqs", tgt_arn))
                        _add_edge(_edge(r_nid, q_nid, "target"))
                    elif ":sns:" in tgt_arn:
                        t_name = tgt_arn.split(":")[-1]
                        t_nid  = f"sns:{t_name}"
                        _add_node(_node(t_nid, t_name, "sns", tgt_arn))
                        _add_edge(_edge(r_nid, t_nid, "target"))
                    elif ":states:" in tgt_arn:
                        sm_name = tgt_arn.split(":")[-1]
                        sm_nid  = f"stepfunctions:{sm_name}"
                        _add_node(_node(sm_nid, sm_name, "stepfunctions", tgt_arn))
                        _add_edge(_edge(r_nid, sm_nid, "target"))

    except Exception:
        pass

    try:
        # ── Step Functions → Lambda ─────────────────────────────────────────
        sf_mod = _loaded_modules.get("stepfunctions")
        if sf_mod:
            for sm_arn, sm in sf_mod._state_machines.items():
                sm_name = sm_arn.split(":")[-1]
                sm_nid  = f"stepfunctions:{sm_name}"
                _add_node(_node(sm_nid, sm_name, "stepfunctions", sm_arn))
                # Parse definition for Lambda Resource ARNs
                try:
                    defn = json.loads(sm.get("definition", "{}"))
                    for state in defn.get("States", {}).values():
                        resource = state.get("Resource", "")
                        if ":lambda:" in resource or "/function:" in resource:
                            fn_name = resource.split(":")[-1].split("/")[-1]
                            fn_nid  = f"lambda:{fn_name}"
                            _add_node(_node(fn_nid, fn_name, "lambda", resource))
                            _add_edge(_edge(sm_nid, fn_nid, "invoke"))
                except Exception:
                    pass

    except Exception:
        pass

    try:
        # ── Standalone SQS queues (not yet in graph) ────────────────────────
        sqs_mod = _loaded_modules.get("sqs")
        if sqs_mod:
            for q_url, q in sqs_mod._queues.items():
                q_name = q_url.split("/")[-1]
                q_nid  = f"sqs:{q_name}"
                _add_node(_node(q_nid, q_name, "sqs",
                                f"arn:aws:sqs:us-east-1:000000000000:{q_name}"))

    except Exception:
        pass

    try:
        # ── DynamoDB tables (standalone) ────────────────────────────────────
        ddb_mod = _loaded_modules.get("dynamodb")
        if ddb_mod:
            for t_name, tbl in ddb_mod._tables.items():
                t_nid = f"dynamodb:{t_name}"
                _add_node(_node(t_nid, t_name, "dynamodb",
                                tbl.get("TableArn", f"arn:aws:dynamodb:us-east-1:000000000000:table/{t_name}")))

    except Exception:
        pass

    try:
        # ── S3 buckets ──────────────────────────────────────────────────────
        s3_mod = _loaded_modules.get("s3")
        if s3_mod:
            for b_name in list(s3_mod._buckets.keys()):
                b_nid = f"s3:{b_name}"
                _add_node(_node(b_nid, b_name, "s3",
                                f"arn:aws:s3:::{b_name}"))

    except Exception:
        pass

    # Only include edges where both nodes exist
    valid_edges = [e for e in edges if e["source"] in seen_nodes and e["target"] in seen_nodes]

    return 200, ct, json.dumps({"nodes": nodes, "edges": valid_edges}).encode()


async def _handle_pumba_jobs(method: str, path: str):
    """GET /_kumostack/chaos/pumba-jobs — list running Pumba jobs."""
    if method != "GET" or path != "/_kumostack/chaos/pumba-jobs":
        return None
    ct = {"Content-Type": "application/json"}
    with _chaos_lock:
        jobs = list(_pumba_jobs.values())
    return 200, ct, json.dumps({"jobs": jobs}).encode()


# ---------------------------------------------------------------------------
# K6 Load Testing control
# ---------------------------------------------------------------------------

_k6_lock = threading.Lock()
_k6_job: dict = {}  # single running job: {id, scenario, vus, duration, status, started_at, container_id}


async def _handle_k6_request(method: str, path: str, body: bytes):
    """Handle /_kumostack/k6/* requests — run/stop/status k6 load tests via Docker."""
    if not path.startswith("/_kumostack/k6"):
        return None
    ct = {"Content-Type": "application/json"}

    # GET /_kumostack/k6/status
    if method == "GET" and path == "/_kumostack/k6/status":
        with _k6_lock:
            job = dict(_k6_job)
        # Refresh container status if running
        if job.get("container_id"):
            dc = _get_docker_client()
            if dc:
                try:
                    c = dc.containers.get(job["container_id"])
                    job["status"] = c.status  # running / exited / …
                    if c.status == "exited":
                        job["exit_code"] = c.wait(timeout=0).get("StatusCode", -1)
                except Exception:
                    job["status"] = "unknown"
        return 200, ct, json.dumps(job).encode()

    # POST /_kumostack/k6/run
    if method == "POST" and path == "/_kumostack/k6/run":
        with _k6_lock:
            if _k6_job.get("status") == "running":
                return 409, ct, json.dumps({"error": "A k6 run is already in progress"}).encode()

        data = json.loads(body or b"{}")
        scenario  = data.get("scenario", "mixed")
        vus       = int(data.get("vus", 10))
        duration  = str(data.get("duration", "60s"))

        valid_scenarios = {"s3", "sqs", "dynamodb", "lambda", "mixed"}
        if scenario not in valid_scenarios:
            return 400, ct, json.dumps({"error": f"scenario must be one of {sorted(valid_scenarios)}"}).encode()

        dc = _get_docker_client()
        if not dc:
            return 503, ct, json.dumps({"error": "Docker not available"}).encode()

        job_id = f"k6-{scenario}-{int(_time.time())}"
        script_path = f"/k6/scenarios/{scenario}.js"

        prom_url = "http://kumostack-prometheus:9090/api/v1/write"

        def _run_k6():
            try:
                container = dc.containers.run(
                    "grafana/k6:latest",
                    command=[
                        "run",
                        "--out", "experimental-prometheus-rw",
                        "--vus",      str(vus),
                        "--duration", duration,
                        script_path,
                    ],
                    environment={
                        "KUMOSTACK_ENDPOINT":       "http://kumostack:4566",
                        "AWS_ACCESS_KEY_ID":        "test",
                        "AWS_SECRET_ACCESS_KEY":    "test",
                        "AWS_REGION":               "us-east-1",
                        "K6_VUS":                   str(vus),
                        "K6_DURATION":              duration,
                        "K6_PROMETHEUS_RW_SERVER_URL":   prom_url,
                        "K6_PROMETHEUS_RW_TREND_STATS":  "p(50),p(95),p(99),avg,min,max",
                    },
                    volumes={
                        "/k6": {"bind": "/k6", "mode": "ro"},
                    },
                    network="kumostack_default",
                    name=f"kumostack-{job_id}",
                    detach=True,
                    remove=False,
                )
                with _k6_lock:
                    _k6_job["container_id"] = container.id
                    _k6_job["status"]       = "running"
                logger.info("K6 job %s started (container %s)", job_id, container.short_id)
                container.wait()
                with _k6_lock:
                    _k6_job["status"] = "completed"
                logger.info("K6 job %s completed", job_id)
            except Exception as exc:
                with _k6_lock:
                    _k6_job["status"] = "error"
                    _k6_job["error"]  = str(exc)
                logger.exception("K6 job %s failed: %s", job_id, exc)

        with _k6_lock:
            _k6_job.clear()
            _k6_job.update({
                "id":           job_id,
                "scenario":     scenario,
                "vus":          vus,
                "duration":     duration,
                "status":       "starting",
                "started_at":   _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                "container_id": None,
            })

        threading.Thread(target=_run_k6, daemon=True, name=f"k6-{job_id}").start()
        return 202, ct, json.dumps({"id": job_id, "status": "starting"}).encode()

    # POST /_kumostack/k6/stop
    if method == "POST" and path == "/_kumostack/k6/stop":
        with _k6_lock:
            cid = _k6_job.get("container_id")
        if not cid:
            return 404, ct, json.dumps({"error": "No running k6 job"}).encode()
        dc = _get_docker_client()
        if dc:
            try:
                dc.containers.get(cid).stop(timeout=5)
            except Exception:
                pass
        with _k6_lock:
            _k6_job["status"] = "stopped"
        return 200, ct, json.dumps({"status": "stopped"}).encode()

    # DELETE /_kumostack/k6/cleanup — remove exited container
    if method == "DELETE" and path == "/_kumostack/k6/cleanup":
        with _k6_lock:
            cid = _k6_job.get("container_id")
        if cid:
            dc = _get_docker_client()
            if dc:
                try:
                    dc.containers.get(cid).remove(force=True)
                except Exception:
                    pass
        with _k6_lock:
            _k6_job.clear()
        return 200, ct, json.dumps({"status": "cleared"}).encode()

    return None


# ---------------------------------------------------------------------------
# ASGI entry point
# ---------------------------------------------------------------------------


async def _periodic_save_loop():
    """Save all service state to disk every 60 seconds when PERSIST_STATE=1."""
    while True:
        await asyncio.sleep(60)
        if not _loaded_modules:
            continue
        save_dict = {}
        for key, mod_name in _state_map.items():
            if mod_name in _loaded_modules:
                save_dict[key] = _loaded_modules[mod_name].get_state
        try:
            save_all(save_dict)
            logger.debug("Periodic state snapshot saved (%d services).", len(save_dict))
        except Exception as e:
            logger.warning("Periodic state save error: %s", e)


async def app(scope, receive, send):
    """ASGI application entry point."""
    if scope["type"] == "lifespan":
        await _handle_lifespan(scope, receive, send)
        return

    if scope["type"] == "websocket":
        # WebSocket APIs are reachable two ways:
        #   ws://{apiId}.execute-api.{host}[:port]/{stage}[/...]           (Host-based)
        #   ws://<host>[:port]/_aws/execute-api/{apiId}/{stage}[/...]      (LocalStack-compat path)
        ws_headers = {}
        for name, value in scope.get("headers", []):
            try:
                ws_headers[name.decode("latin-1").lower()] = value.decode("utf-8")
            except UnicodeDecodeError:
                ws_headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        ws_host = ws_headers.get("host", "")
        ws_path = scope.get("path", "")
        parsed = _parse_execute_api_url(ws_host, ws_path)
        appsync_rt_m = _APPSYNC_REALTIME_RE.match(ws_host)
        iot_ws_m = _IOT_DATA_WS_RE.search(ws_host) and _ws_has_mqtt_subprotocol(ws_headers)
        if not parsed and not appsync_rt_m and not iot_ws_m:
            msg = await receive()
            if msg.get("type") == "websocket.connect":
                await send({"type": "websocket.close", "code": 1008})
            return
        try:
            if parsed:
                ws_api_id, _stage, _execute_path = parsed
                await _get_module("apigateway").handle_websocket(
                    scope, receive, send, ws_api_id, path_override=_execute_path,
                )
            elif appsync_rt_m:
                await _get_module("appsync_events").handle_websocket(
                    scope, receive, send, appsync_rt_m.group(1)
                )
            else:
                # IoT MQTT-over-WS — resolve account_id from SigV4 query
                # params or Authorization header, fall back to default.
                account_id = _ws_resolve_iot_account_id(scope, ws_headers)
                await _get_module("iot").handle_websocket(
                    scope, receive, send, account_id
                )
        except Exception:
            logger.exception("Error in WebSocket dispatch")
            try:
                await send({"type": "websocket.close", "code": 1011})
            except Exception:
                pass
        return

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]
    query_string = scope.get("query_string", b"").decode("utf-8")
    query_params = parse_qs(query_string, keep_blank_values=True)

    headers = {}
    for name, value in scope.get("headers", []):
        try:
            headers[name.decode("latin-1").lower()] = value.decode("utf-8")
        except UnicodeDecodeError:
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")

    request_id = str(uuid.uuid4())

    # If a /_kumostack/reset is in flight, wait for it to finish before
    # serving this request. The lock is uncontended in steady state
    # (acquire/release is near-free); during a reset, new requests block
    # until state-wipe completes so no test can observe a half-reset server.
    if path != "/_kumostack/reset":
        async with _get_reset_lock():
            pass

    # Set per-request account ID from credentials (multi-tenancy support).
    # If the access key is a 12-digit number, it becomes the account ID.
    _access_key = extract_access_key_id(headers)
    if _access_key:
        set_request_account_id(_access_key)

    # Set per-request region from SigV4 Credential scope so CFN's AWS::Region
    # pseudo-param and ARN-building use the caller's region, not MINISTACK_REGION
    # (issue #398). Falls back to MINISTACK_REGION env.
    set_request_region(extract_region(headers))

    if await _send_if_handled(send, await _handle_pre_body_request(method, path, headers, query_params, request_id)):
        return

    body = await _read_request_body(receive, method, headers)

    if await _send_if_handled(send, await _handle_post_body_shortcuts(method, path, headers, body, query_params, request_id)):
        return

    if await _send_if_handled(
        send, await _handle_special_data_plane_request(method, path, headers, body, query_params, request_id)
    ):
        return

    await _send_response(send, *await _dispatch_service_request(method, path, headers, body, query_params, request_id))


# ---------------------------------------------------------------------------
# Lifecycle, init scripts, and server administration
# ---------------------------------------------------------------------------


async def _handle_lifespan(scope, receive, send):
    """Handle ASGI lifespan events."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            port = _resolve_port()
            logger.info(BANNER.format(port=port))
            # Install a larger default thread-pool executor. Lambda invocations
            # (warm pool subprocess spawn, RIE HTTP, provided-runtime) all ride
            # on asyncio.to_thread; Python's default is min(32, cpu+4) which
            # is only 6 on a 2-core CI runner. Under xdist that queues cold
            # starts behind other blocking work and test urlopen timeouts fire
            # before the handler ever runs. 64 is plenty — threads are cheap
            # and idle. Override with MINISTACK_WORKER_THREADS.
            import concurrent.futures

            _max_workers = int(os.environ.get("MINISTACK_WORKER_THREADS", "64"))
            asyncio.get_running_loop().set_default_executor(
                concurrent.futures.ThreadPoolExecutor(
                    max_workers=_max_workers,
                    thread_name_prefix="kumostack-worker",
                )
            )
            logger.info("Worker thread pool: %d threads", _max_workers)
            _run_init_scripts()
            # Reap any container that survived a hard kill of the previous
            # process. Persistence strips container ids from snapshots, so any
            # kumostack-labelled container alive at boot is by definition an
            # orphan whose name will collide on next create.
            _stop_docker_containers()
            if PERSIST_STATE:
                _load_persisted_state()
            # Start the Transfer Family SFTP listener after persistence is
            # loaded (so any restored Transfer servers/users are visible to
            # the SSH auth callback). When the user opts out via
            # SFTP_ENABLED=0 we skip importing the transfer module entirely
            # — its top-level `import asyncssh` pulls cryptography+OpenSSL
            # (~2–4 MiB of heap, plus C-level SSL contexts) which is pure
            # overhead for callers that aren't using Transfer Family.
            _sftp_env = os.environ.get("SFTP_ENABLED", "").strip().lower()
            if _sftp_env in ("0", "false", "no", "off"):
                logger.debug("SFTP_ENABLED=%s — skipping transfer module import.", _sftp_env)
            else:
                try:
                    from kumostack.services import transfer

                    await transfer.sftp_start()
                except Exception as e:
                    logger.warning("Transfer SFTP startup failed: %s", e)
            # Start the EventBridge scheduler daemon explicitly. Module-import
            # autostart is gated by MINISTACK_TEST_NO_AUTOSTART so unit tests
            # don't race; lifespan.startup is the canonical place to spin it up.
            try:
                from kumostack.services import eventbridge as _eb_mod
                _eb_mod.start_scheduler()
            except Exception as e:
                logger.warning("EventBridge scheduler startup failed: %s", e)
            await send({"type": "lifespan.startup.complete"})
            logger.info("Ready — %d services available on port %s.", len(SERVICE_HANDLERS), port)
            # Per-service "init completed" lines are logged at DEBUG only — at
            # INFO they bury the operational signal (CreateBucket, etc.) under
            # a wall of one line per service.
            for svc in SERVICE_HANDLERS:
                logger.debug("%s init completed.", svc.capitalize())
            asyncio.create_task(_run_ready_scripts())
            if PERSIST_STATE:
                asyncio.create_task(_periodic_save_loop())
        elif message["type"] == "lifespan.shutdown":
            logger.info("KumoStack shutting down...")
            if PERSIST_STATE:
                # Only save state for modules that were actually loaded
                save_dict = {}
                for key, mod_name in _state_map.items():
                    if mod_name in _loaded_modules:
                        save_dict[key] = _loaded_modules[mod_name].get_state
                save_all(save_dict)
            try:
                from kumostack.services import transfer

                await transfer.sftp_stop()
            except Exception as e:
                logger.debug("Transfer SFTP shutdown error: %s", e)
            _stop_docker_containers()
            await send({"type": "lifespan.shutdown.complete"})
            return


def _stop_docker_containers():
    """Stop all Docker containers managed by KumoStack (RDS, ECS, ElastiCache).
    Uses container labels to find them — does not touch service state.

    Skip entirely if no Docker socket is available: importing the docker
    SDK (and its requests/urllib3/idna transitive deps) costs ~1 MiB of
    Python heap before we even know whether there's anything to clean.
    """
    sock = os.environ.get("DOCKER_HOST") or "unix:///var/run/docker.sock"
    if sock.startswith("unix://"):
        sock_path = sock[len("unix://"):]
        if not os.path.exists(sock_path):
            return
    try:
        import docker

        client = docker.from_env()
    except Exception:
        return
    for label in ("kumostack=rds", "kumostack=ecs", "kumostack=elasticache", "kumostack=eks", "kumostack=lambda"):
        try:
            # all=True so exited-but-not-removed orphans get cleaned at boot.
            for c in client.containers.list(all=True, filters={"label": label}):
                try:
                    c.stop(timeout=5)
                    c.remove(v=True)
                except Exception:
                    pass
        except Exception:
            pass


def _load_persisted_state():
    """Load persisted state for services that support it."""
    for svc_key in ("apigateway", "apigateway_v1", "servicediscovery"):
        data = load_state(svc_key)
        if data:
            _get_module(svc_key).load_persisted_state(data)
            logger.info("Loaded persisted state for %s", svc_key)

    # Eagerly import persisted services whose restore path depends on
    # a module-level `load_state()` side-effect, but which would not
    # otherwise be imported during startup. These are NOT covered by
    # the explicit central-restore loop above (no
    # `load_persisted_state` method), and the lazy router will not
    # pull them in early enough — for example, `ses_v2` is reached
    # via the `/v2/email/*` path-prefix shortcut and `pipes` via
    # CloudFormation, neither of which fires at lifespan startup.
    # Importing here triggers the restore (and, for `pipes`, also
    # restarts the background poller for any RUNNING pipe). Keep this
    # list narrow — every entry costs a cold-start import. Enforced
    # by `tests/test_persistence_symmetry.py::test_state_map_
    # services_without_endpoint_are_eagerly_imported`.
    for svc_key in ("pipes", "ses_v2"):
        _get_module(svc_key)


async def _wait_for_port(port, timeout=30):
    """Wait until the server is accepting TCP connections."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError:
            await asyncio.sleep(0.1)
    logger.warning("Server did not become ready within %ds — skipping ready.d scripts", timeout)


async def _run_ready_scripts():
    """Execute .sh/.py scripts from ready.d directories after the server is ready."""
    scripts = _collect_scripts("/docker-entrypoint-initaws.d/ready.d", "/etc/localstack/init/ready.d")
    if not scripts:
        _ready_scripts_state.update({"status": "completed", "total": 0, "completed": 0, "failed": 0})
        return
    _ready_scripts_state.update({"status": "running", "total": len(scripts), "completed": 0, "failed": 0})
    port = int(_resolve_port())
    await _wait_for_port(port)
    logger.info("Found %d ready script(s)", len(scripts))
    # Provide sensible defaults so init scripts can use aws cli / boto3
    # without requiring manual credential configuration.  Skip credential
    # defaults when the user has mounted ~/.aws/credentials so the CLI
    # respects their configured profile.
    script_env = {**os.environ}
    _creds_paths = [os.path.expanduser("~/.aws"), "/root/.aws"]
    _custom_creds = os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    _has_creds_file = (_custom_creds and os.path.isfile(_custom_creds)) or any(
        os.path.isfile(os.path.join(d, "credentials")) for d in _creds_paths
    )
    if not _has_creds_file:
        script_env.setdefault("AWS_ACCESS_KEY_ID", "test")
        script_env.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    script_env.setdefault("AWS_DEFAULT_REGION", os.environ.get("MINISTACK_REGION", "us-east-1"))
    script_env.setdefault("AWS_ENDPOINT_URL", f"http://{_MINISTACK_HOST}:{port}")
    for ready_dir in ("/docker-entrypoint-initaws.d/ready.d", "/etc/localstack/init/ready.d"):
        if os.path.isdir(ready_dir):
            script_env.setdefault("KUMOSTACK_INIT_READY_DIR", ready_dir)
            script_env.setdefault("MINISTACK_INIT_READY_DIR", ready_dir)
            break
    for script_path in scripts:
        logger.info("Running ready script: %s", script_path)
        script_failed = False
        try:
            cmd = [sys.executable, script_path] if script_path.endswith(".py") else ["sh", script_path]
            per_script_env = {
                **script_env,
                "KUMOSTACK_INIT_SCRIPT_DIR": os.path.dirname(script_path),
                "KUMOSTACK_INIT_SCRIPT_PATH": script_path,
                "MINISTACK_INIT_SCRIPT_DIR": os.path.dirname(script_path),
                "MINISTACK_INIT_SCRIPT_PATH": script_path,
            }
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=per_script_env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            if stdout:
                logger.info("  stdout: %s", stdout.decode("utf-8", errors="replace").rstrip())
            if proc.returncode != 0:
                script_failed = True
                logger.error(
                    "Ready script %s failed (exit %d): %s",
                    script_path,
                    proc.returncode,
                    stderr.decode("utf-8", errors="replace"),
                )
            else:
                logger.info("Ready script %s completed successfully", script_path)
        except asyncio.TimeoutError:
            script_failed = True
            logger.error("Ready script %s timed out after 300s", script_path)
            proc.kill()
        except Exception as e:
            script_failed = True
            logger.error("Failed to execute ready script %s: %s", script_path, e)
        _ready_scripts_state["completed"] += 1
        if script_failed:
            _ready_scripts_state["failed"] += 1
    _ready_scripts_state["status"] = "completed"


def _collect_scripts(*dirs):
    """Collect .sh/.py scripts from multiple directories, deduped by filename."""
    seen = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith((".sh", ".py")) and f not in seen:
                seen[f] = os.path.join(d, f)
    return [seen[f] for f in sorted(seen)]


def _run_init_scripts():
    """Execute .sh/.py scripts from init directories in alphabetical order."""
    scripts = _collect_scripts("/docker-entrypoint-initaws.d", "/etc/localstack/init/boot.d")
    if not scripts:
        return
    logger.info("Found %d init script(s)", len(scripts))
    base_env = {**os.environ}
    for boot_dir in ("/docker-entrypoint-initaws.d", "/etc/localstack/init/boot.d"):
        if os.path.isdir(boot_dir):
            base_env.setdefault("KUMOSTACK_INIT_BOOT_DIR", boot_dir)
            base_env.setdefault("MINISTACK_INIT_BOOT_DIR", boot_dir)
            break
    for script_path in scripts:
        logger.info("Running init script: %s", script_path)
        try:
            cmd = [sys.executable, script_path] if script_path.endswith(".py") else ["sh", script_path]
            per_script_env = {
                **base_env,
                "KUMOSTACK_INIT_SCRIPT_DIR": os.path.dirname(script_path),
                "KUMOSTACK_INIT_SCRIPT_PATH": script_path,
                "MINISTACK_INIT_SCRIPT_DIR": os.path.dirname(script_path),
                "MINISTACK_INIT_SCRIPT_PATH": script_path,
            }
            result = subprocess.run(
                cmd,
                env=per_script_env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.stdout:
                logger.info("  stdout: %s", result.stdout.rstrip())
            if result.returncode != 0:
                logger.error("Init script %s failed (exit %d): %s", script_path, result.returncode, result.stderr)
            else:
                logger.info("Init script %s completed successfully", script_path)
        except subprocess.TimeoutExpired:
            logger.error("Init script %s timed out after 300s", script_path)
        except Exception as e:
            logger.error("Failed to execute init script %s: %s", script_path, e)


def _reset_all_state():
    """Wipe all in-memory state across every service module, and persisted files if enabled."""

    from kumostack.core.persistence import PERSIST_STATE, STATE_DIR

    # Stateful modules that don't have a routing entry in SERVICE_REGISTRY but
    # still need reset() — REST API v1 (served via the apigateway module),
    # SES v2 (served via the ses module), and EventBridge Pipes (CFN-only
    # provisioner with a background poller thread that reset() must stop).
    _extra_reset_modules = ("apigateway_v1", "ses_v2", "pipes")

    module_names = {cfg["module"] for cfg in SERVICE_REGISTRY.values()}
    module_names.update(_extra_reset_modules)

    for mod_name in module_names:
        if mod_name in _loaded_modules:
            mod = _loaded_modules[mod_name]
            try:
                mod.reset()
            except Exception as e:
                logger.warning("reset() failed for %s: %s", mod_name, e)

    S3_DATA_DIR = os.environ.get("S3_DATA_DIR", "/tmp/kumostack-data/s3")
    S3_PERSIST = os.environ.get("S3_PERSIST", "0") == "1"

    # Wipe persisted files so a subsequent restart doesn't reload old state
    if PERSIST_STATE and os.path.isdir(STATE_DIR):
        for fname in os.listdir(STATE_DIR):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(STATE_DIR, fname))
                except Exception as e:
                    logger.warning("reset: failed to remove %s: %s", fname, e)
        logger.info("Wiped persisted state files in %s", STATE_DIR)

    if S3_PERSIST and os.path.isdir(S3_DATA_DIR):
        for entry in os.listdir(S3_DATA_DIR):
            entry_path = os.path.join(S3_DATA_DIR, entry)
            try:
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
                else:
                    os.remove(entry_path)
            except Exception as e:
                logger.warning("reset: failed to remove S3 data %s: %s", entry, e)
        logger.info("Wiped S3 persisted data in %s", S3_DATA_DIR)

    logger.info("State reset complete")


def _pid_file(port: int) -> str:
    return os.path.join(tempfile.gettempdir(), f"kumostack-{port}.pid")


def main():
    from hypercorn.asyncio import serve as hypercorn_serve
    from hypercorn.config import Config as HypercornConfig

    parser = argparse.ArgumentParser(description="KumoStack — Local AWS Service Emulator")
    parser.add_argument("-d", "--detach", action="store_true", help="Run in the background (detached mode)")
    parser.add_argument("--stop", action="store_true", help="Stop a detached KumoStack server")
    args = parser.parse_args()

    port = int(_resolve_port())
    # BIND_HOST controls the bind interface; defaults to 0.0.0.0 (existing
    # behaviour). Distinct from MINISTACK_HOST, which is the virtual hostname
    # used for S3 virtual-host / execute-api URL matching.
    bind_host = os.environ.get("BIND_HOST", "0.0.0.0")

    if args.stop:
        pf = _pid_file(port)
        if not os.path.exists(pf):
            print(f"No KumoStack PID file found for port {port}. Is it running?")
            raise SystemExit(1)
        with open(pf) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"KumoStack (PID {pid}) on port {port} stopped.")
        except ProcessLookupError:
            print(f"KumoStack (PID {pid}) was not running. Cleaning up PID file.")
        os.remove(pf)
        return

    # 0.0.0.0 binds every interface so 127.0.0.1 always works as a probe;
    # for an explicit BIND_HOST, probe that host directly.
    probe_host = "127.0.0.1" if bind_host == "0.0.0.0" else bind_host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((probe_host, port)) == 0:
            print(
                f"ERROR: {probe_host}:{port} is already in use. Is KumoStack already running?\n"
                f"  Stop it with: kumostack --stop\n"
                f"  Or use a different port: GATEWAY_PORT=4567 kumostack"
            )
            raise SystemExit(1)

    if args.detach:
        log_file = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"kumostack-{port}.log")
        # Keep a reference to the log file handle — Popen inherits the fd so
        # closing it here would break child process logging.  The handle is
        # intentionally kept open for the lifetime of this (short-lived) parent
        # process; the OS reclaims it when the parent exits.
        log_fh = open(log_file, "w")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "hypercorn",
                "kumostack.app:app",
                "--bind",
                f"{bind_host}:{port}",
                "--log-level",
                LOG_LEVEL.upper(),
                "--keep-alive",
                "75",
            ],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pf = _pid_file(port)
        with open(pf, "w") as f:
            f.write(str(proc.pid))
        print(f"KumoStack started in background (PID {proc.pid}) on port {port}.")
        print(f"  Logs: {log_file}")
        print("  Stop: kumostack --stop")
        return

    # Foreground — write PID file and clean up on exit
    pf = _pid_file(port)
    with open(pf, "w") as f:
        f.write(str(os.getpid()))

    def _cleanup(*_):
        try:
            os.remove(pf)
        except OSError:
            pass

    signal.signal(signal.SIGTERM, lambda *_: (_cleanup(), sys.exit(0)))
    try:
        # Suppress health-check access logs at INFO level (reported by @McDoit).
        # Visible when LOG_LEVEL=DEBUG.
        class _HealthLogFilter(logging.Filter):
            def filter(self, record):
                if LOG_LEVEL == "DEBUG":
                    return True
                return not any(p in record.getMessage() for p in _HEALTH_PATHS)

        logging.getLogger("hypercorn.access").addFilter(_HealthLogFilter())

        config = HypercornConfig()
        config.bind = [f"{bind_host}:{port}"]
        config.keep_alive_timeout = 75
        config.loglevel = LOG_LEVEL.upper()

        # USE_SSL=1 enables HTTPS — matches the behaviour previously provided
        # by kumostack/core/hypercorn_conf.py when the entrypoint was the
        # hypercorn CLI. Self-signed cert auto-generated under TMPDIR, or BYO
        # via MINISTACK_SSL_CERT + MINISTACK_SSL_KEY.
        from kumostack.core import tls as _tls
        if _tls.use_ssl_enabled():
            config.certfile, config.keyfile = _tls.resolve_tls_material()

        asyncio.run(hypercorn_serve(app, config))
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
