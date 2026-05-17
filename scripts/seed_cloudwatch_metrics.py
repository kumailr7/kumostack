#!/usr/bin/env python3
"""
Seed CloudWatch metrics for ALL AWS Grafana dashboards in KumoStack.
Covers every namespace used by the 20 pre-built dashboards.
Publishes metrics at both aggregate (no dims) and per-resource (with dims)
levels so SEARCH-expression panels work out of the box.

Usage:
  python3 scripts/seed_cloudwatch_metrics.py                 # one-time
  python3 scripts/seed_cloudwatch_metrics.py --backfill 30   # fill last 30 min
  python3 scripts/seed_cloudwatch_metrics.py --loop          # seed every 60 s
  python3 scripts/seed_cloudwatch_metrics.py --backfill 30 --loop
"""
import argparse, datetime, os, random, time
import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL",
           os.environ.get("KUMOSTACK_ENDPOINT", "http://localhost:4566"))
REGION   = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

BOTO = dict(endpoint_url=ENDPOINT, region_name=REGION,
            aws_access_key_id="test", aws_secret_access_key="test")

cw  = boto3.client("cloudwatch",  **BOTO)


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def _v(base: float, jitter: float = 0.25) -> float:
    return max(0.0, base * (1 + random.uniform(-jitter, jitter)))

def _put(namespace: str, data: list):
    for i in range(0, len(data), 20):
        cw.put_metric_data(Namespace=namespace, MetricData=data[i:i+20])

def _m(name, value, unit, dims=None, ts=None):
    m = {"MetricName": name, "Value": float(value), "Unit": unit,
         "Timestamp": ts or now()}
    if dims:
        m["Dimensions"] = dims
    return m

# ── helpers ───────────────────────────────────────────────────────────────────

def _client(svc): return boto3.client(svc, **BOTO)

def _list_lambda():
    try: return _client("lambda").list_functions().get("Functions", [])
    except: return []

def _list_ddb():
    try: return _client("dynamodb").list_tables().get("TableNames", [])
    except: return []

def _list_sqs():
    try: return _client("sqs").list_queues().get("QueueUrls", [])
    except: return []

def _list_sns():
    try: return [t["TopicArn"] for t in _client("sns").list_topics().get("Topics", [])]
    except: return []

def _list_s3():
    try: return [b["Name"] for b in _client("s3").list_buckets().get("Buckets", [])]
    except: return []

def _list_cloudfront():
    try:
        items = _client("cloudfront").list_distributions()\
            .get("DistributionList", {}).get("Items", [])
        return [d["Id"] for d in items]
    except: return []

def _list_rds():
    try: return [d["DBInstanceIdentifier"]
                 for d in _client("rds").describe_db_instances().get("DBInstances", [])]
    except: return []

def _list_elasticache():
    try: return [c["CacheClusterId"]
                 for c in _client("elasticache").describe_cache_clusters().get("CacheClusters", [])]
    except: return []

def _list_apigateway():
    try: return [a["name"] for a in _client("apigateway").get_rest_apis().get("items", [])]
    except: return []

# ── Lambda ────────────────────────────────────────────────────────────────────

def seed_lambda(ts=None):
    fns = _list_lambda()
    data, ai, ae, at, ad = [], 0, 0, 0, 0.0
    for fn in fns:
        n = fn["FunctionName"]
        i=int(_v(80)); e=int(_v(4)); t=int(_v(1)); d=_v(280)
        ai+=i; ae+=e; at+=t; ad+=d
        dim=[{"Name":"FunctionName","Value":n}]
        data+=[_m("Invocations",i,"Count",dim,ts),_m("Errors",e,"Count",dim,ts),
               _m("Throttles",t,"Count",dim,ts),_m("Duration",d,"Milliseconds",dim,ts),
               _m("ConcurrentExecutions",int(_v(5)),"Count",dim,ts)]
    n=max(len(fns),1)
    data+=[_m("Invocations",ai,"Count",None,ts),_m("Errors",ae,"Count",None,ts),
           _m("Throttles",at,"Count",None,ts),_m("Duration",ad/n,"Milliseconds",None,ts),
           _m("ConcurrentExecutions",int(_v(10)),"Count",None,ts)]
    _put("AWS/Lambda", data); return len(fns)

# ── DynamoDB ──────────────────────────────────────────────────────────────────

def seed_dynamodb(ts=None):
    tables = _list_ddb()
    data, ar, aw = [], 0.0, 0.0
    for t in tables:
        rcu=_v(10); wcu=_v(5); ar+=rcu; aw+=wcu
        dim=[{"Name":"TableName","Value":t}]
        data+=[_m("ConsumedReadCapacityUnits",rcu,"Count",dim,ts),
               _m("ConsumedWriteCapacityUnits",wcu,"Count",dim,ts),
               _m("ProvisionedReadCapacityUnits",_v(25),"Count",dim,ts),
               _m("ProvisionedWriteCapacityUnits",_v(25),"Count",dim,ts),
               _m("ReadThrottleEvents",int(_v(0.5)),"Count",dim,ts),
               _m("WriteThrottleEvents",int(_v(0.2)),"Count",dim,ts),
               _m("SuccessfulRequestLatency",_v(2),"Milliseconds",
                  [*dim,{"Name":"Operation","Value":"GetItem"}],ts),
               _m("SuccessfulRequestLatency",_v(3),"Milliseconds",
                  [*dim,{"Name":"Operation","Value":"PutItem"}],ts)]
    data+=[_m("ConsumedReadCapacityUnits",ar,"Count",None,ts),
           _m("ConsumedWriteCapacityUnits",aw,"Count",None,ts),
           _m("ProvisionedReadCapacityUnits",_v(25),"Count",None,ts),
           _m("ProvisionedWriteCapacityUnits",_v(25),"Count",None,ts),
           _m("ReadThrottleEvents",int(_v(0.5)),"Count",None,ts),
           _m("WriteThrottleEvents",int(_v(0.2)),"Count",None,ts),
           _m("SuccessfulRequestLatency",_v(2),"Milliseconds",[{"Name":"Operation","Value":"GetItem"}],ts),
           _m("SuccessfulRequestLatency",_v(3),"Milliseconds",[{"Name":"Operation","Value":"PutItem"}],ts)]
    _put("AWS/DynamoDB", data); return len(tables)

# ── SQS ───────────────────────────────────────────────────────────────────────

def seed_sqs(ts=None):
    urls = _list_sqs()
    data, as_, ar, av, ad = [], 0, 0, 0, 0
    for url in urls:
        name=url.split("/")[-1]; s=int(_v(40)); r=int(_v(35)); v=int(_v(5)); d=int(_v(30))
        as_+=s; ar+=r; av+=v; ad+=d
        dim=[{"Name":"QueueName","Value":name}]
        data+=[_m("NumberOfMessagesSent",s,"Count",dim,ts),
               _m("NumberOfMessagesReceived",r,"Count",dim,ts),
               _m("ApproximateNumberOfMessagesVisible",v,"Count",dim,ts),
               _m("NumberOfMessagesDeleted",d,"Count",dim,ts),
               _m("SentMessageSize",_v(1024),"Bytes",dim,ts)]
    data+=[_m("NumberOfMessagesSent",as_,"Count",None,ts),
           _m("NumberOfMessagesReceived",ar,"Count",None,ts),
           _m("ApproximateNumberOfMessagesVisible",av,"Count",None,ts),
           _m("NumberOfMessagesDeleted",ad,"Count",None,ts),
           _m("SentMessageSize",_v(1024),"Bytes",None,ts)]
    _put("AWS/SQS", data); return len(urls)

# ── SNS ───────────────────────────────────────────────────────────────────────

def seed_sns(ts=None):
    arns = _list_sns()
    data, ap, ad_, af = [], 0, 0, 0
    for arn in arns:
        name=arn.split(":")[-1]; p=int(_v(30)); d=int(_v(28)); f=int(_v(1))
        ap+=p; ad_+=d; af+=f
        dim=[{"Name":"TopicName","Value":name}]
        data+=[_m("NumberOfMessagesPublished",p,"Count",dim,ts),
               _m("NumberOfNotificationsDelivered",d,"Count",dim,ts),
               _m("NumberOfNotificationsFailed",f,"Count",dim,ts),
               _m("PublishSize",_v(512),"Bytes",dim,ts)]
    data+=[_m("NumberOfMessagesPublished",ap,"Count",None,ts),
           _m("NumberOfNotificationsDelivered",ad_,"Count",None,ts),
           _m("NumberOfNotificationsFailed",af,"Count",None,ts),
           _m("PublishSize",_v(512),"Bytes",None,ts)]
    _put("AWS/SNS", data); return len(arns)

# ── S3 ────────────────────────────────────────────────────────────────────────

INFRA_BUCKETS = {"ministack-logs","kumostack-logs","logs-cold-archive","logs-rds-archive"}

def seed_s3(ts=None):
    buckets = [b for b in _list_s3() if b not in INFRA_BUCKETS]
    data = []
    for name in buckets:
        dim=[{"Name":"BucketName","Value":name},{"Name":"StorageType","Value":"StandardStorage"}]
        data+=[_m("BucketSizeBytes",_v(5e6),"Bytes",dim,ts),
               _m("NumberOfObjects",_v(120),"Count",dim,ts)]
    n=max(len(buckets),1)
    data+=[_m("BucketSizeBytes",_v(5e6*n),"Bytes",None,ts),
           _m("NumberOfObjects",_v(120*n),"Count",None,ts),
           _m("AllRequests",int(_v(200)),"Count",None,ts),
           _m("GetRequests",int(_v(150)),"Count",None,ts),
           _m("PutRequests",int(_v(50)),"Count",None,ts),
           _m("4xxErrors",int(_v(2)),"Count",None,ts),
           _m("5xxErrors",0,"Count",None,ts)]
    _put("AWS/S3", data); return len(buckets)

# ── CloudFront ────────────────────────────────────────────────────────────────

def seed_cloudfront(ts=None):
    dist_ids = _list_cloudfront()
    # Always seed aggregate (Region=Global) so the dashboard panel gets data
    # even when no distributions exist
    data = []
    agg_req = 0
    for dist_id in dist_ids:
        req = int(_v(5000)); err4 = int(_v(100)); err5 = int(_v(20)); miss = int(_v(1000))
        agg_req += req
        dim  = [{"Name":"DistributionId","Value":dist_id},{"Name":"Region","Value":"Global"}]
        data += [
            _m("Requests",           req,             "None",    dim, ts),
            _m("BytesDownloaded",    _v(50e6),        "None",    dim, ts),
            _m("BytesUploaded",      _v(1e6),         "None",    dim, ts),
            _m("TotalErrorRate",     (err4+err5)/req*100 if req else 0, "Percent", dim, ts),
            _m("4xxErrorRate",       err4/req*100 if req else 0, "Percent", dim, ts),
            _m("5xxErrorRate",       err5/req*100 if req else 0, "Percent", dim, ts),
            _m("CacheHitRate",       _v(80),          "Percent", dim, ts),
            _m("LambdaExecutionError", int(_v(2)),    "None",    dim, ts),
            _m("OriginLatency",      _v(45),          "Milliseconds", dim, ts),
        ]
    # Aggregate (no DistributionId dim)
    global_dim = [{"Name":"Region","Value":"Global"}]
    req_agg = agg_req or int(_v(5000))
    data += [
        _m("Requests",          req_agg,             "None",    global_dim, ts),
        _m("BytesDownloaded",   _v(50e6),            "None",    global_dim, ts),
        _m("BytesUploaded",     _v(1e6),             "None",    global_dim, ts),
        _m("TotalErrorRate",    _v(2),               "Percent", global_dim, ts),
        _m("4xxErrorRate",      _v(1.5),             "Percent", global_dim, ts),
        _m("5xxErrorRate",      _v(0.5),             "Percent", global_dim, ts),
        _m("CacheHitRate",      _v(82),              "Percent", global_dim, ts),
        _m("OriginLatency",     _v(45),              "Milliseconds", global_dim, ts),
        # Also publish with no dims at all for panels with matchExact=false
        _m("Requests",          req_agg,             "None",    None, ts),
        _m("BytesDownloaded",   _v(50e6),            "None",    None, ts),
        _m("BytesUploaded",     _v(1e6),             "None",    None, ts),
        _m("TotalErrorRate",    _v(2),               "Percent", None, ts),
        _m("4xxErrorRate",      _v(1.5),             "Percent", None, ts),
        _m("5xxErrorRate",      _v(0.5),             "Percent", None, ts),
        _m("CacheHitRate",      _v(82),              "Percent", None, ts),
        _m("OriginLatency",     _v(45),              "Milliseconds", None, ts),
    ]
    _put("AWS/CloudFront", data)
    return len(dist_ids)

# ── RDS ───────────────────────────────────────────────────────────────────────

def seed_rds(ts=None):
    instances = _list_rds()
    data = []
    for ident in instances:
        dim=[{"Name":"DBInstanceIdentifier","Value":ident}]
        data+=[_m("CPUUtilization",_v(20),"Percent",dim,ts),
               _m("DatabaseConnections",_v(5),"Count",dim,ts),
               _m("FreeStorageSpace",_v(20e9),"Bytes",dim,ts),
               _m("ReadLatency",_v(0.005),"Seconds",dim,ts),
               _m("WriteLatency",_v(0.003),"Seconds",dim,ts),
               _m("ReadIOPS",_v(100),"Count/Second",dim,ts),
               _m("WriteIOPS",_v(50),"Count/Second",dim,ts),
               _m("FreeableMemory",_v(2e9),"Bytes",dim,ts),
               _m("NetworkReceiveThroughput",_v(1e6),"Bytes/Second",dim,ts),
               _m("NetworkTransmitThroughput",_v(2e6),"Bytes/Second",dim,ts)]
    # aggregate
    data+=[_m("CPUUtilization",_v(20),"Percent",None,ts),
           _m("DatabaseConnections",_v(5),"Count",None,ts),
           _m("ReadLatency",_v(0.005),"Seconds",None,ts),
           _m("WriteLatency",_v(0.003),"Seconds",None,ts),
           _m("ReadIOPS",_v(100),"Count/Second",None,ts),
           _m("WriteIOPS",_v(50),"Count/Second",None,ts)]
    _put("AWS/RDS", data); return len(instances)

# ── ElastiCache ───────────────────────────────────────────────────────────────

def seed_elasticache(ts=None):
    clusters = _list_elasticache()
    data = []
    for cid in clusters:
        dim=[{"Name":"CacheClusterId","Value":cid}]
        data+=[_m("CPUUtilization",_v(15),"Percent",dim,ts),
               _m("CacheHits",_v(100),"Count",dim,ts),
               _m("CacheMisses",_v(10),"Count",dim,ts),
               _m("CurrConnections",_v(8),"Count",dim,ts),
               _m("NetworkBytesIn",_v(4096),"Bytes",dim,ts),
               _m("NetworkBytesOut",_v(8192),"Bytes",dim,ts),
               _m("Evictions",int(_v(2)),"Count",dim,ts),
               _m("GetTypeCmds",int(_v(500)),"Count",dim,ts),
               _m("SetTypeCmds",int(_v(100)),"Count",dim,ts)]
    data+=[_m("CPUUtilization",_v(15),"Percent",None,ts),
           _m("CacheHits",_v(100),"Count",None,ts),
           _m("CacheMisses",_v(10),"Count",None,ts),
           _m("CurrConnections",_v(8),"Count",None,ts),
           _m("NetworkBytesIn",_v(4096),"Bytes",None,ts),
           _m("NetworkBytesOut",_v(8192),"Bytes",None,ts),
           _m("Evictions",int(_v(2)),"Count",None,ts)]
    _put("AWS/ElastiCache", data); return len(clusters)

# ── API Gateway ───────────────────────────────────────────────────────────────

def seed_apigateway(ts=None):
    apis = _list_apigateway()
    data = []
    for name in apis:
        dim=[{"Name":"ApiName","Value":name}]
        data+=[_m("Count",int(_v(200)),"Count",dim,ts),
               _m("4XXError",int(_v(5)),"Count",dim,ts),
               _m("5XXError",int(_v(1)),"Count",dim,ts),
               _m("Latency",_v(120),"Milliseconds",dim,ts),
               _m("IntegrationLatency",_v(90),"Milliseconds",dim,ts)]
    data+=[_m("Count",int(_v(200)),"Count",None,ts),
           _m("4XXError",int(_v(5)),"Count",None,ts),
           _m("5XXError",int(_v(1)),"Count",None,ts),
           _m("Latency",_v(120),"Milliseconds",None,ts),
           _m("IntegrationLatency",_v(90),"Milliseconds",None,ts)]
    _put("AWS/ApiGateway", data); return len(apis)

# ── EC2 + EBS ─────────────────────────────────────────────────────────────────

def seed_ec2(ts=None):
    data = [
        _m("CPUUtilization",       _v(30),   "Percent",      None, ts),
        _m("NetworkIn",            _v(1e6),  "Bytes",        None, ts),
        _m("NetworkOut",           _v(2e6),  "Bytes",        None, ts),
        _m("NetworkPacketsIn",     _v(1000), "Count",        None, ts),
        _m("NetworkPacketsOut",    _v(1500), "Count",        None, ts),
        _m("StatusCheckFailed",    0,        "Count",        None, ts),
        _m("StatusCheckFailed_Instance", 0,  "Count",        None, ts),
        _m("StatusCheckFailed_System",   0,  "Count",        None, ts),
        _m("CPUCreditBalance",     _v(100),  "Count",        None, ts),
        _m("CPUCreditUsage",       _v(5),    "Count",        None, ts),
    ]
    _put("AWS/EC2", data)
    ebs = [
        _m("VolumeReadBytes",      _v(512e3),    "Bytes",        None, ts),
        _m("VolumeWriteBytes",     _v(1e6),      "Bytes",        None, ts),
        _m("VolumeReadOps",        int(_v(100)), "Count",        None, ts),
        _m("VolumeWriteOps",       int(_v(200)), "Count",        None, ts),
        _m("VolumeTotalReadTime",  _v(0.05),     "Seconds",      None, ts),
        _m("VolumeTotalWriteTime", _v(0.1),      "Seconds",      None, ts),
        _m("VolumeIdleTime",       _v(59),       "Seconds",      None, ts),
        _m("VolumeQueueLength",    _v(0.5),      "Count",        None, ts),
        _m("BurstBalance",         _v(90),       "Percent",      None, ts),
    ]
    _put("AWS/EBS", ebs)
    return 0  # synthetic — no real EC2 instances

# ── Application Load Balancer ─────────────────────────────────────────────────

def seed_alb(ts=None):
    # Discover real ALB names from KumoStack
    try:
        albs = _client("elbv2").describe_load_balancers().get("LoadBalancers", [])
        lb_names = [lb["LoadBalancerName"] for lb in albs if lb.get("Type") == "application"]
    except Exception:
        lb_names = []
    if not lb_names:
        lb_names = ["kumostack-cluster-alb"]

    metrics = [
        ("RequestCount",              int(_v(500)),  "Count"),
        ("NewConnectionCount",        int(_v(50)),   "Count"),
        ("ActiveConnectionCount",     int(_v(30)),   "Count"),
        ("ProcessedBytes",            _v(10e6),      "Bytes"),
        ("TargetResponseTime",        _v(0.08),      "Seconds"),
        ("HTTPCode_Target_2XX_Count", int(_v(480)),  "Count"),
        ("HTTPCode_Target_4XX_Count", int(_v(15)),   "Count"),
        ("HTTPCode_Target_5XX_Count", int(_v(5)),    "Count"),
        ("HTTPCode_ELB_4XX_Count",    int(_v(5)),    "Count"),
        ("HTTPCode_ELB_5XX_Count",    int(_v(2)),    "Count"),
        ("HealthyHostCount",          _v(2),         "Count"),
        ("UnHealthyHostCount",        0,             "Count"),
        ("RejectedConnectionCount",   0,             "Count"),
    ]
    # Aggregate (no dims) + per-LB dims so SEARCH() and direct queries both work
    data = [_m(name, val, unit, None, ts) for name, val, unit in metrics]
    for lb in lb_names:
        dims = [{"Name": "LoadBalancer", "Value": lb}]
        data += [_m(name, val, unit, dims, ts) for name, val, unit in metrics]
    _put("AWS/ApplicationELB", data)
    return 0


# ── EKS / ContainerInsights ───────────────────────────────────────────────────

def seed_eks(ts=None):
    # Discover real EKS clusters from KumoStack
    try:
        clusters = _client("eks").list_clusters().get("clusters", [])
    except Exception:
        clusters = []
    if not clusters:
        clusters = ["kumostack-cluster"]

    for cluster in clusters:
        cdims = [{"Name": "ClusterName", "Value": cluster}]

        # AWS/EKS namespace — basic cluster metrics
        eks_metrics = [
            ("cluster_failed_node_count",         0,            "Count"),
            ("cluster_node_count",                _v(1),        "Count"),
            ("namespace_number_of_running_pods",  _v(3),        "Count"),
        ]
        data_eks = [_m(name, val, unit, cdims, ts) for name, val, unit in eks_metrics]
        _put("AWS/EKS", data_eks)

        # ContainerInsights namespace — pod/node level metrics
        node_id = "ip-172-25-0-3.ec2.internal"
        ndims = cdims + [{"Name": "NodeName", "Value": node_id}]
        pdims = cdims + [
            {"Name": "Namespace",    "Value": "myapp"},
            {"Name": "PodName",      "Value": "sample-app"},
        ]
        svcdims = cdims + [
            {"Name": "Namespace",    "Value": "myapp"},
            {"Name": "Service",      "Value": "sample-app"},
        ]

        ci_metrics = []
        # Cluster-level
        for name, val, unit in [
            ("cluster_failed_node_count",        0,          "Count"),
            ("cluster_node_count",               _v(1),      "Count"),
            ("namespace_number_of_running_pods", _v(3),      "Count"),
        ]:
            ci_metrics.append(_m(name, val, unit, cdims, ts))

        # Node-level
        for name, val, unit in [
            ("node_cpu_utilization",             _v(18),     "Percent"),
            ("node_memory_utilization",          _v(42),     "Percent"),
            ("node_network_total_bytes",         _v(5e6),    "Bytes"),
            ("node_cpu_limit",                   2000,       "Millicores"),
            ("node_memory_limit",                _v(2e9),    "Bytes"),
            ("node_number_of_running_pods",      _v(3),      "Count"),
        ]:
            ci_metrics.append(_m(name, val, unit, ndims, ts))

        # Pod-level
        for name, val, unit in [
            ("pod_cpu_utilization",              _v(5),      "Percent"),
            ("pod_memory_utilization",           _v(38),     "Percent"),
            ("pod_network_rx_bytes",             _v(1e5),    "Bytes"),
            ("pod_network_tx_bytes",             _v(8e4),    "Bytes"),
            ("pod_number_of_container_restarts", 0,          "Count"),
        ]:
            ci_metrics.append(_m(name, val, unit, pdims, ts))

        # Service-level
        for name, val, unit in [
            ("service_number_of_running_pods",   _v(1),      "Count"),
        ]:
            ci_metrics.append(_m(name, val, unit, svcdims, ts))

        _put("ContainerInsights", ci_metrics)
    return 0

# ── ECS ───────────────────────────────────────────────────────────────────────

def seed_ecs(ts=None):
    data = [
        _m("CPUUtilization",    _v(25),   "Percent", None, ts),
        _m("MemoryUtilization", _v(40),   "Percent", None, ts),
        _m("CPUReservation",    _v(30),   "Percent", None, ts),
        _m("MemoryReservation", _v(50),   "Percent", None, ts),
    ]
    _put("AWS/ECS", data)
    return 0

# ── EFS ───────────────────────────────────────────────────────────────────────

def seed_efs(ts=None):
    data = [
        _m("ClientConnections",    int(_v(10)),   "Count",        None, ts),
        _m("DataReadIOBytes",      _v(1e6),       "Bytes",        None, ts),
        _m("DataWriteIOBytes",     _v(2e6),       "Bytes",        None, ts),
        _m("MetadataIOBytes",      _v(100e3),     "Bytes",        None, ts),
        _m("TotalIOBytes",         _v(3e6),       "Bytes",        None, ts),
        _m("PercentIOLimit",       _v(5),         "Percent",      None, ts),
        _m("BurstCreditBalance",   _v(2e12),      "Bytes",        None, ts),
        _m("StorageBytes",         _v(10e9),      "Bytes",        None, ts),
    ]
    _put("AWS/EFS", data)
    return 0

# ── Kinesis ───────────────────────────────────────────────────────────────────

def seed_kinesis(ts=None):
    data = [
        _m("GetRecords.Bytes",                    _v(1e6),      "Bytes",    None, ts),
        _m("GetRecords.IteratorAgeMilliseconds",  _v(100),      "Milliseconds", None, ts),
        _m("GetRecords.Latency",                  _v(50),       "Milliseconds", None, ts),
        _m("GetRecords.Records",                  int(_v(100)), "Count",    None, ts),
        _m("GetRecords.Success",                  1,            "Count",    None, ts),
        _m("IncomingBytes",                       _v(2e6),      "Bytes",    None, ts),
        _m("IncomingRecords",                     int(_v(200)), "Count",    None, ts),
        _m("PutRecord.Bytes",                     _v(10e3),     "Bytes",    None, ts),
        _m("PutRecord.Latency",                   _v(20),       "Milliseconds", None, ts),
        _m("PutRecord.Success",                   1,            "Count",    None, ts),
        _m("PutRecords.Bytes",                    _v(100e3),    "Bytes",    None, ts),
        _m("PutRecords.Latency",                  _v(30),       "Milliseconds", None, ts),
        _m("PutRecords.Success",                  1,            "Count",    None, ts),
        _m("ReadProvisionedThroughputExceeded",   0,            "Count",    None, ts),
        _m("WriteProvisionedThroughputExceeded",  0,            "Count",    None, ts),
    ]
    _put("AWS/Kinesis", data)
    return 0

# ── Step Functions ────────────────────────────────────────────────────────────

def seed_stepfunctions(ts=None):
    data = [
        _m("ExecutionsStarted",       int(_v(50)),   "Count",        None, ts),
        _m("ExecutionsSucceeded",     int(_v(46)),   "Count",        None, ts),
        _m("ExecutionsFailed",        int(_v(2)),    "Count",        None, ts),
        _m("ExecutionsAborted",       0,             "Count",        None, ts),
        _m("ExecutionsTimedOut",      0,             "Count",        None, ts),
        _m("ExecutionThrottled",      0,             "Count",        None, ts),
        _m("ExecutionTime",           _v(2500),      "Milliseconds", None, ts),
    ]
    _put("AWS/States", data)
    return 0

# ── Cognito ───────────────────────────────────────────────────────────────────

def seed_cognito(ts=None):
    data = [
        _m("SignInSuccesses",       int(_v(100)), "Count", None, ts),
        _m("SignInThrottles",       0,            "Count", None, ts),
        _m("SignUpSuccesses",       int(_v(10)),  "Count", None, ts),
        _m("SignUpThrottles",       0,            "Count", None, ts),
        _m("TokenRefreshSuccesses", int(_v(200)), "Count", None, ts),
        _m("TokenRefreshThrottles", 0,            "Count", None, ts),
        _m("FederationSuccesses",   int(_v(20)),  "Count", None, ts),
    ]
    _put("AWS/Cognito", data)
    return 0

# ── CodeBuild ─────────────────────────────────────────────────────────────────

def seed_codebuild(ts=None):
    data = [
        _m("Builds",            int(_v(10)),   "Count",        None, ts),
        _m("SucceededBuilds",   int(_v(9)),    "Count",        None, ts),
        _m("FailedBuilds",      int(_v(1)),    "Count",        None, ts),
        _m("Duration",          _v(180),       "Seconds",      None, ts),
        _m("BuildDuration",     _v(160),       "Seconds",      None, ts),
    ]
    _put("AWS/CodeBuild", data)
    return 0

# ── SES ───────────────────────────────────────────────────────────────────────

def seed_ses(ts=None):
    data = [
        _m("Send",              int(_v(500)),  "Count", None, ts),
        _m("Delivery",          int(_v(490)),  "Count", None, ts),
        _m("Bounce",            int(_v(5)),    "Count", None, ts),
        _m("Complaint",         int(_v(1)),    "Count", None, ts),
        _m("Reject",            0,             "Count", None, ts),
        _m("Open",              int(_v(200)),  "Count", None, ts),
        _m("Click",             int(_v(50)),   "Count", None, ts),
        _m("RenderingFailure",  0,             "Count", None, ts),
    ]
    _put("AWS/SES", data)
    return 0

# ── EMR ───────────────────────────────────────────────────────────────────────

def seed_emr(ts=None):
    data = [
        _m("IsIdle",                0,           "Count", None, ts),
        _m("CoreNodesPending",      0,           "Count", None, ts),
        _m("LiveDataNodes",         _v(2),       "Count", None, ts),
        _m("MRActiveNodes",         _v(2),       "Count", None, ts),
        _m("HDFSUtilization",       _v(30),      "Percent", None, ts),
        _m("YARNMemoryAvailablePercentage", _v(70), "Percent", None, ts),
        _m("ContainerAllocated",    int(_v(4)),  "Count", None, ts),
        _m("ContainerPending",      0,           "Count", None, ts),
        _m("ContainerReserved",     0,           "Count", None, ts),
    ]
    _put("AWS/ElasticMapReduce", data)
    return 0

# ── WAF ───────────────────────────────────────────────────────────────────────

def seed_waf(ts=None):
    data = [
        _m("AllowedRequests",        int(_v(1000)), "Count", None, ts),
        _m("BlockedRequests",        int(_v(50)),   "Count", None, ts),
        _m("CountedRequests",        int(_v(20)),   "Count", None, ts),
        _m("PassedRequests",         int(_v(980)),  "Count", None, ts),
        _m("RequestsWithValidToken", int(_v(500)),  "Count", None, ts),
        _m("ChallengeRequests",      int(_v(10)),   "Count", None, ts),
    ]
    _put("AWS/WAFV2", data)
    return 0

# ── Main ──────────────────────────────────────────────────────────────────────

SEEDERS = [
    ("Lambda",       seed_lambda),
    ("DynamoDB",     seed_dynamodb),
    ("SQS",          seed_sqs),
    ("SNS",          seed_sns),
    ("S3",           seed_s3),
    ("CloudFront",   seed_cloudfront),
    ("RDS",          seed_rds),
    ("ElastiCache",  seed_elasticache),
    ("APIGateway",   seed_apigateway),
    ("EC2/EBS",      seed_ec2),
    ("ALB",          seed_alb),
    ("EKS",          seed_eks),
    ("ECS",          seed_ecs),
    ("EFS",          seed_efs),
    ("Kinesis",      seed_kinesis),
    ("StepFunctions",seed_stepfunctions),
    ("Cognito",      seed_cognito),
    ("CodeBuild",    seed_codebuild),
    ("SES",          seed_ses),
    ("EMR",          seed_emr),
    ("WAF",          seed_waf),
]


def seed_all(ts=None, verbose=True):
    label = (ts or datetime.datetime.now(datetime.timezone.utc)).strftime("%H:%M:%S")
    parts = []
    for name, fn in SEEDERS:
        try:
            n = fn(ts)
            if n: parts.append(f"{name}:{n}")
        except Exception as e:
            if verbose: parts.append(f"{name}:ERR({e})")
    if verbose:
        print(f"[{label}] {' '.join(parts) or 'seeded (synthetic)'}")


def backfill(minutes: int, interval_s: int = 60):
    now = datetime.datetime.now(datetime.timezone.utc)
    steps = (minutes * 60) // interval_s
    print(f"Backfilling {steps} points ({minutes} min, every {interval_s}s) …")
    for i in range(steps, 0, -1):
        t = now - datetime.timedelta(seconds=i * interval_s)
        seed_all(ts=t, verbose=False)
    print("Backfill complete.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0, metavar="MINUTES")
    ap.add_argument("--loop",     action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    args = ap.parse_args()

    if args.backfill:
        backfill(args.backfill)

    if args.loop:
        print(f"Seeding every {args.interval}s — Ctrl-C to stop.")
        while True:
            seed_all()
            time.sleep(args.interval)
    elif not args.backfill:
        seed_all()
