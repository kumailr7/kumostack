# Copyright (c) 2026 KumoStack Contributors
# Licensed under the MIT License. See LICENSE for details.
"""
AWS X-Ray Service Emulator.

Implements the X-Ray HTTP management API and stores trace segments
in memory.  Each accepted segment is also forwarded to Grafana Tempo
via OTLP/HTTP so traces appear natively in Grafana Explore.

Supported operations
──────────────────────────────────────────────────────────────────────
PutTraceSegments      POST /TraceSegments
GetTraceSummaries     POST /TraceSummaries
BatchGetTraces        POST /Traces
GetServiceGraph       POST /ServiceGraph
GetGroups             POST /Groups
PutTelemetryRecords   POST /TelemetryRecords  (accepted, ignored)
"""

import json
import logging
import os
import threading
import time
import urllib.request
import uuid
from collections import defaultdict
from typing import Any

logger = logging.getLogger("xray")

# ── Config ─────────────────────────────────────────────────────────────────────

_TEMPO_OTLP_URL = os.environ.get(
    "TEMPO_OTLP_URL", "http://kumostack-tempo:4318/v1/traces"
)
_TEMPO_ENABLED = os.environ.get("TEMPO_ENABLED", "1") not in ("0", "false", "")

# ── In-memory store ────────────────────────────────────────────────────────────

_lock = threading.Lock()

# trace_id → list of segment dicts
_traces: dict[str, list[dict]] = {}

# service_name → set of downstream service names (for service graph)
_service_graph: dict[str, set] = defaultdict(set)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _new_trace_id() -> str:
    epoch = format(int(time.time()), "08x")
    rand  = uuid.uuid4().hex[:24]
    return f"1-{epoch}-{rand}"


def _xray_id_to_otlp_trace(trace_id: str) -> str:
    """Convert X-Ray trace ID  1-XXXXXXXX-YYYYYYYYYYYYYYYYYYYYYYYY  →  32 hex (16 bytes)."""
    try:
        parts = trace_id.split("-")
        return (parts[1] + parts[2]).zfill(32)
    except Exception:
        return uuid.uuid4().hex


def _xray_id_to_otlp_span(segment_id: str) -> str:
    """X-Ray segment IDs are already 16 hex chars (8 bytes) — pass through."""
    return segment_id.ljust(16, "0")[:16]


def _epoch_to_nano(ts: float) -> int:
    return int(ts * 1_000_000_000)


def _segment_to_otlp_spans(segment: dict, trace_id_hex: str, parent_span_id: str | None = None) -> list[dict]:
    """Recursively convert an X-Ray segment + its subsegments to OTLP spans."""
    span_id = _xray_id_to_otlp_span(segment.get("id", uuid.uuid4().hex[:16]))
    name    = segment.get("name", "unknown")
    start   = _epoch_to_nano(segment.get("start_time", time.time()))
    end     = _epoch_to_nano(segment.get("end_time",   segment.get("start_time", time.time()) + 0.001))

    attrs: list[dict] = []

    http = segment.get("http", {})
    req  = http.get("request", {})
    resp = http.get("response", {})
    if req.get("method"): attrs.append({"key": "http.method",      "value": {"stringValue": req["method"]}})
    if req.get("url"):    attrs.append({"key": "http.url",         "value": {"stringValue": req["url"]}})
    if resp.get("status"):attrs.append({"key": "http.status_code", "value": {"intValue":    int(resp["status"])}})

    aws = segment.get("aws", {})
    if aws.get("operation"):   attrs.append({"key": "aws.operation",   "value": {"stringValue": aws["operation"]}})
    if aws.get("table_name"):  attrs.append({"key": "aws.table",       "value": {"stringValue": aws["table_name"]}})
    if aws.get("queue_url"):   attrs.append({"key": "aws.queue_url",   "value": {"stringValue": aws["queue_url"]}})
    if aws.get("function_name"): attrs.append({"key": "aws.function",  "value": {"stringValue": aws["function_name"]}})
    if aws.get("bucket_name"): attrs.append({"key": "aws.s3.bucket",  "value": {"stringValue": aws["bucket_name"]}})

    namespace = segment.get("namespace", "")
    if namespace: attrs.append({"key": "aws.namespace", "value": {"stringValue": namespace}})

    error    = segment.get("error", False)
    fault    = segment.get("fault", False)
    status   = {"code": 2} if (error or fault) else {"code": 1}
    if error or fault:
        attrs.append({"key": "error", "value": {"boolValue": True}})

    # SPAN_KIND_SERVER for root, SPAN_KIND_CLIENT for subsegments / aws calls
    kind = 2 if parent_span_id is None else (3 if namespace == "aws" else 3)

    span: dict[str, Any] = {
        "traceId":             trace_id_hex,
        "spanId":              span_id,
        "name":                name,
        "kind":                kind,
        "startTimeUnixNano":   str(start),
        "endTimeUnixNano":     str(end),
        "attributes":          attrs,
        "status":              status,
    }
    if parent_span_id:
        span["parentSpanId"] = parent_span_id

    spans = [span]
    for sub in segment.get("subsegments", []):
        spans.extend(_segment_to_otlp_spans(sub, trace_id_hex, parent_span_id=span_id))

    return spans


def _forward_to_tempo(segment: dict) -> None:
    if not _TEMPO_ENABLED:
        return
    try:
        trace_id_hex = _xray_id_to_otlp_trace(segment.get("trace_id", _new_trace_id()))
        spans        = _segment_to_otlp_spans(segment, trace_id_hex)

        payload = {
            "resourceSpans": [{
                "resource": {
                    "attributes": [{
                        "key":   "service.name",
                        "value": {"stringValue": segment.get("name", "kumostack")},
                    }]
                },
                "scopeSpans": [{
                    "scope": {"name": "kumostack-xray", "version": "1.0"},
                    "spans": spans,
                }],
            }]
        }
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            _TEMPO_OTLP_URL, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception as exc:
        logger.debug("Tempo forward failed (will retry next segment): %s", exc)


# ── Storage helpers ────────────────────────────────────────────────────────────


def _store_segment(seg: dict) -> None:
    tid = seg.get("trace_id") or _new_trace_id()
    seg["trace_id"] = tid
    with _lock:
        _traces.setdefault(tid, []).append(seg)
        # Update service graph — root segments declare downstream calls via subsegments
        root_name = seg.get("name", "")
        if root_name:
            for sub in seg.get("subsegments", []):
                sub_name = sub.get("name", "")
                if sub_name:
                    _service_graph[root_name].add(sub_name)
    threading.Thread(target=_forward_to_tempo, args=(seg,), daemon=True).start()


def _build_summary(trace_id: str, segments: list[dict]) -> dict:
    root    = next((s for s in segments if not s.get("parent_id")), segments[0])
    has_err = any(s.get("error") or s.get("fault") for s in segments)
    dur     = 0.0
    if root.get("start_time") and root.get("end_time"):
        dur = root["end_time"] - root["start_time"]

    http = root.get("http", {})
    resp = http.get("response", {})

    return {
        "Id":         trace_id,
        "Duration":   round(dur, 4),
        "HasError":   any(s.get("error") for s in segments),
        "HasFault":   any(s.get("fault") for s in segments),
        "HasThrottle":any(s.get("throttle") for s in segments),
        "IsPartial":  False,
        "ResponseTime": round(dur, 4),
        "Http": {
            "HttpMethod": http.get("request", {}).get("method", ""),
            "HttpUrl":    http.get("request", {}).get("url", ""),
            "HttpStatus": resp.get("status", 0),
        },
        "ServiceIds": [{"Name": s.get("name", ""), "Type": s.get("type", "AWS::Other")} for s in segments],
        "Users": [],
        "Annotations": root.get("annotations", {}),
    }


# ── handle_request ─────────────────────────────────────────────────────────────


async def handle_request(method: str, path: str, headers: dict, body: bytes, query_params: dict):
    ct = {"Content-Type": "application/json"}

    # ── PutTraceSegments ────────────────────────────────────────────────────────
    if path == "/TraceSegments" and method == "POST":
        data = json.loads(body or b"{}")
        docs = data.get("TraceSegmentDocuments", [])
        unprocessed = []
        for raw in docs:
            try:
                seg = json.loads(raw) if isinstance(raw, str) else raw
                _store_segment(seg)
            except Exception as exc:
                logger.warning("Failed to parse segment: %s", exc)
                unprocessed.append({"Id": "", "ErrorCode": "InvalidSegmentShape", "Message": str(exc)})
        return 200, ct, json.dumps({"UnprocessedTraceSegments": unprocessed}).encode()

    # ── PutTelemetryRecords ─────────────────────────────────────────────────────
    if path == "/TelemetryRecords" and method == "POST":
        return 200, ct, b"{}"

    # ── GetTraceSummaries ───────────────────────────────────────────────────────
    if path == "/TraceSummaries" and method == "POST":
        data     = json.loads(body or b"{}")
        start    = float(data.get("StartTime", 0))
        end      = float(data.get("EndTime",   time.time()))
        filter_  = (data.get("FilterExpression") or "").lower()

        with _lock:
            snapshot = dict(_traces)

        summaries = []
        for tid, segs in snapshot.items():
            root = next((s for s in segs if not s.get("parent_id")), segs[0] if segs else None)
            if not root:
                continue
            ts = root.get("start_time", 0)
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            if filter_:
                combined = json.dumps(root).lower()
                if filter_ not in combined:
                    continue
            summaries.append(_build_summary(tid, segs))

        summaries.sort(key=lambda s: s.get("Duration", 0), reverse=True)
        return 200, ct, json.dumps({
            "TraceSummaries":    summaries,
            "ApproximateTime":   time.time(),
            "TracesProcessedCount": len(summaries),
        }).encode()

    # ── BatchGetTraces ──────────────────────────────────────────────────────────
    if path == "/Traces" and method == "POST":
        data = json.loads(body or b"{}")
        ids  = data.get("TraceIds", [])
        traces_out = []
        unprocessed = []
        with _lock:
            for tid in ids:
                segs = _traces.get(tid)
                if segs:
                    traces_out.append({
                        "Id":       tid,
                        "Duration": 0,
                        "Segments": [{"Id": s.get("id", ""), "Document": json.dumps(s)} for s in segs],
                    })
                else:
                    unprocessed.append(tid)
        return 200, ct, json.dumps({"Traces": traces_out, "UnprocessedTraceIds": unprocessed}).encode()

    # ── GetServiceGraph ─────────────────────────────────────────────────────────
    if path == "/ServiceGraph" and method == "POST":
        with _lock:
            graph = {k: list(v) for k, v in _service_graph.items()}

        services = []
        seen: set[str] = set()

        def _make_service(name: str, svc_type: str = "AWS::Other") -> dict:
            return {
                "Name":        name,
                "Type":        svc_type,
                "StartTime":   time.time() - 3600,
                "EndTime":     time.time(),
                "Edges":       [],
                "SummaryStatistics": {"OkCount": 0, "ErrorStatistics": {"ThrottleCount": 0, "OtherCount": 0, "TotalCount": 0}, "FaultStatistics": {"TotalCount": 0, "OtherCount": 0}, "TotalCount": 0, "TotalResponseTime": 0},
            }

        for src, dsts in graph.items():
            if src not in seen:
                svc = _make_service(src, "AWS::EC2::Instance")
                svc["Edges"] = [{"ReferenceId": i, "StartTime": time.time() - 3600, "EndTime": time.time()} for i, _ in enumerate(dsts)]
                services.append(svc)
                seen.add(src)
            for dst in dsts:
                if dst not in seen:
                    services.append(_make_service(dst, "AWS::DynamoDB::Table" if "dynamo" in dst.lower() else "AWS::Lambda::Function" if "lambda" in dst.lower() else "AWS::SQS::Queue" if "sqs" in dst.lower() else "AWS::S3::Bucket" if "s3" in dst.lower() else "AWS::Other"))
                    seen.add(dst)

        return 200, ct, json.dumps({
            "Services":  services,
            "StartTime": time.time() - 3600,
            "EndTime":   time.time(),
        }).encode()

    # ── GetGroups ───────────────────────────────────────────────────────────────
    if path == "/Groups" and method == "POST":
        return 200, ct, json.dumps({"Groups": [], "NextToken": None}).encode()

    # ── /_kumostack/xray/traces (dashboard list endpoint) ───────────────────────
    if path == "/_kumostack/xray/traces" and method == "GET":
        limit = int(query_params.get("limit", ["50"])[0])
        with _lock:
            snapshot = dict(_traces)
        summaries = []
        for tid, segs in snapshot.items():
            if segs:
                summaries.append(_build_summary(tid, segs))
        summaries.sort(key=lambda s: s.get("Duration", 0), reverse=True)
        return 200, ct, json.dumps({"traces": summaries[:limit], "total": len(summaries)}).encode()

    # ── /_kumostack/xray/clear (dev helper) ────────────────────────────────────
    if path == "/_kumostack/xray/clear" and method == "DELETE":
        with _lock:
            _traces.clear()
            _service_graph.clear()
        return 200, ct, b'{"status":"cleared"}'

    return 404, ct, json.dumps({"message": f"X-Ray: unknown path {path}"}).encode()
