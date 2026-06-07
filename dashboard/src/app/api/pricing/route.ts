import { NextResponse } from "next/server";

// ── In-memory cache (1 hour TTL) ──────────────────────────────────────────────
let _cache: { data: PricingResponse; ts: number } | null = null;
const TTL_MS = 60 * 60 * 1000;

export interface ServicePrice {
  service:       string;
  key:           string;
  description:   string;
  metrics:       { label: string; price: string; unit: string; detail: string }[];
  free_tier:     string;
  pricing_url:   string;
  calculator_url: string;
  source:        "aws-live" | "curated";
}

export interface PricingResponse {
  fetched_at:    string;
  region:        "us-east-1";
  services:      ServicePrice[];
}

// ── Curated baseline — us-east-1 on-demand (updated 2026) ─────────────────────
const CURATED: Omit<ServicePrice, "source">[] = [
  {
    service: "Lambda",
    key: "lambda",
    description: "Serverless compute — billed per invocation and duration. No charge when idle.",
    metrics: [
      { label: "Requests",     price: "$0.20",      unit: "per 1M requests",      detail: "First 1M/month free" },
      { label: "Duration",     price: "$0.0000166667", unit: "per GB-second",      detail: "First 400,000 GB-s/month free" },
      { label: "Provisioned",  price: "$0.0000097222", unit: "per GB-second",      detail: "Provisioned concurrency" },
    ],
    free_tier: "1M requests + 400,000 GB-seconds per month, always free",
    pricing_url: "https://aws.amazon.com/lambda/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/Lambda",
  },
  {
    service: "DynamoDB",
    key: "dynamodb",
    description: "Serverless NoSQL — on-demand capacity charges per request. No minimum fee.",
    metrics: [
      { label: "Write Request Unit", price: "$1.25",  unit: "per 1M WRUs",  detail: "On-demand mode" },
      { label: "Read Request Unit",  price: "$0.25",  unit: "per 1M RRUs",  detail: "On-demand mode" },
      { label: "Storage",            price: "$0.25",  unit: "per GB-month", detail: "First 25 GB free" },
      { label: "Global Tables",      price: "$1.875", unit: "per 1M rWCUs", detail: "Replicated write capacity" },
    ],
    free_tier: "25 GB storage + 25 WCUs + 25 RCUs per month, always free",
    pricing_url: "https://aws.amazon.com/dynamodb/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/DynamoDB",
  },
  {
    service: "S3",
    key: "s3",
    description: "Object storage — pay for storage, requests, and data transfer. No upfront cost.",
    metrics: [
      { label: "Storage (Standard)", price: "$0.023",  unit: "per GB-month",   detail: "First 50 TB/month" },
      { label: "PUT / COPY / POST",  price: "$0.005",  unit: "per 1K requests", detail: "Writes and lists" },
      { label: "GET / HEAD",         price: "$0.0004", unit: "per 1K requests", detail: "Reads" },
      { label: "Data Transfer Out",  price: "$0.09",   unit: "per GB",          detail: "First 100 GB/month free" },
    ],
    free_tier: "5 GB storage + 20K GET + 2K PUT requests for 12 months",
    pricing_url: "https://aws.amazon.com/s3/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/S3",
  },
  {
    service: "SQS",
    key: "sqs",
    description: "Managed message queuing — Standard and FIFO. Priced per API request.",
    metrics: [
      { label: "Standard Queue",     price: "$0.40",  unit: "per 1M requests",  detail: "First 1M/month free" },
      { label: "FIFO Queue",         price: "$0.50",  unit: "per 1M requests",  detail: "Higher ordering guarantee" },
      { label: "Data Transfer",      price: "$0.00",  unit: "within same region", detail: "Free within region" },
    ],
    free_tier: "1M requests per month, always free",
    pricing_url: "https://aws.amazon.com/sqs/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/SQS",
  },
  {
    service: "SNS",
    key: "sns",
    description: "Pub/sub messaging — fan-out notifications to Lambda, SQS, HTTP endpoints.",
    metrics: [
      { label: "API Requests",       price: "$0.50",  unit: "per 1M requests",   detail: "First 1M/month free" },
      { label: "HTTP/HTTPS delivery",price: "$0.60",  unit: "per 1M deliveries", detail: "Notifications to endpoints" },
      { label: "SQS delivery",       price: "$0.00",  unit: "free",              detail: "SNS → SQS is free" },
      { label: "Email",              price: "$2.00",  unit: "per 100K emails",   detail: "Via SNS email protocol" },
    ],
    free_tier: "1M requests + 100K HTTP deliveries per month, always free",
    pricing_url: "https://aws.amazon.com/sns/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/SNS",
  },
  {
    service: "API Gateway",
    key: "apigateway",
    description: "Managed API frontend — REST, HTTP, and WebSocket APIs.",
    metrics: [
      { label: "REST API Calls",     price: "$3.50",  unit: "per 1M calls",       detail: "First 1M/month free (12 mo)" },
      { label: "HTTP API Calls",     price: "$1.00",  unit: "per 1M calls",        detail: "~71% cheaper than REST" },
      { label: "WebSocket Messages", price: "$1.00",  unit: "per 1M messages",     detail: "Connection + messaging" },
      { label: "Cache",              price: "$0.020", unit: "per hour (0.5 GB)",   detail: "Optional response cache" },
    ],
    free_tier: "1M REST calls + 1M HTTP calls per month for 12 months",
    pricing_url: "https://aws.amazon.com/api-gateway/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/APIGateway",
  },
  {
    service: "EventBridge",
    key: "eventbridge",
    description: "Serverless event bus — routes events between AWS services and SaaS applications.",
    metrics: [
      { label: "Custom Events",      price: "$1.00",  unit: "per 1M events",       detail: "First 1M/month free" },
      { label: "Cross-account",      price: "$1.00",  unit: "per 1M events",        detail: "Events across accounts" },
      { label: "Schema discovery",   price: "$0.10",  unit: "per 1M events",        detail: "Auto-discovery" },
    ],
    free_tier: "1M events per month, always free",
    pricing_url: "https://aws.amazon.com/eventbridge/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/EventBridge",
  },
  {
    service: "Kinesis Data Streams",
    key: "kinesis",
    description: "Real-time data streaming — handles millions of events per second.",
    metrics: [
      { label: "Shard Hour",         price: "$0.015", unit: "per shard-hour",       detail: "1 shard = 1MB/s in, 2MB/s out" },
      { label: "PUT Payload Unit",   price: "$0.014", unit: "per 1M units",          detail: "Each 25KB = 1 unit" },
      { label: "Enhanced Fan-out",   price: "$0.015", unit: "per shard-hour",        detail: "Dedicated 2MB/s consumer" },
      { label: "Extended Retention", price: "$0.023", unit: "per shard-hour",        detail: "7–365 day retention" },
    ],
    free_tier: "None (no free tier for Kinesis Data Streams)",
    pricing_url: "https://aws.amazon.com/kinesis/data-streams/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/Kinesis",
  },
  {
    service: "Step Functions",
    key: "stepfunctions",
    description: "Visual workflow orchestration — coordinate Lambda, ECS, DynamoDB, and 200+ services.",
    metrics: [
      { label: "Standard Workflows",  price: "$0.025", unit: "per 1K state transitions", detail: "First 4K/month free" },
      { label: "Express Workflows",   price: "$1.00",  unit: "per 1M executions",         detail: "For high-volume, short-duration" },
      { label: "Express Duration",    price: "$0.00001", unit: "per GB-second",            detail: "Memory × duration" },
    ],
    free_tier: "4,000 state transitions per month, always free",
    pricing_url: "https://aws.amazon.com/step-functions/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/StepFunctions",
  },
  {
    service: "RDS",
    key: "rds",
    description: "Managed relational databases — MySQL, PostgreSQL, MariaDB, Oracle, SQL Server.",
    metrics: [
      { label: "db.t3.micro (MySQL)", price: "$0.017",  unit: "per hour",             detail: "~$12.41/month" },
      { label: "db.m5.large (MySQL)", price: "$0.171",  unit: "per hour",             detail: "~$124.83/month" },
      { label: "Storage (gp2)",       price: "$0.115",  unit: "per GB-month",         detail: "SSD general purpose" },
      { label: "Multi-AZ premium",    price: "2×",      unit: "instance price",       detail: "High availability" },
    ],
    free_tier: "750 hr db.t2.micro for 12 months + 20 GB storage",
    pricing_url: "https://aws.amazon.com/rds/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/RDS",
  },
  {
    service: "ElastiCache",
    key: "elasticache",
    description: "In-memory caching — Redis and Memcached. Sub-millisecond latency at scale.",
    metrics: [
      { label: "cache.t3.micro",      price: "$0.017",  unit: "per hour",             detail: "~$12.41/month" },
      { label: "cache.r6g.large",     price: "$0.166",  unit: "per hour",             detail: "Memory-optimised" },
      { label: "Serverless (ECU)",    price: "$0.0034", unit: "per ElastiCache Unit",  detail: "Auto-scales to demand" },
    ],
    free_tier: "750 hr cache.t2.micro for 12 months",
    pricing_url: "https://aws.amazon.com/elasticache/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/ElastiCache",
  },
  {
    service: "EKS",
    key: "eks",
    description: "Managed Kubernetes — AWS handles the control plane. You pay for worker nodes separately.",
    metrics: [
      { label: "Cluster",             price: "$0.10",  unit: "per hour",              detail: "~$73/month per cluster" },
      { label: "EC2 worker (t3.medium)", price: "$0.0416", unit: "per hour",          detail: "Node group pricing" },
      { label: "Fargate pod (vCPU)",  price: "$0.04048", unit: "per vCPU-hour",       detail: "Serverless node option" },
    ],
    free_tier: "None for the cluster; worker nodes follow EC2/Fargate pricing",
    pricing_url: "https://aws.amazon.com/eks/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/EKS",
  },
  {
    service: "CloudWatch",
    key: "cloudwatch",
    description: "Observability — metrics, logs, dashboards, alarms, and Synthetics canaries.",
    metrics: [
      { label: "Custom Metrics",      price: "$0.30",  unit: "per metric-month",      detail: "First 10 metrics free" },
      { label: "API requests",        price: "$0.01",  unit: "per 1K requests",       detail: "GetMetricData, etc." },
      { label: "Log ingestion",       price: "$0.50",  unit: "per GB",                detail: "First 5 GB/month free" },
      { label: "Log storage",         price: "$0.03",  unit: "per GB-month",          detail: "After 5 GB free" },
    ],
    free_tier: "10 metrics + 3 dashboards + 5 GB logs per month",
    pricing_url: "https://aws.amazon.com/cloudwatch/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/CloudWatch",
  },
  {
    service: "Secrets Manager",
    key: "secretsmanager",
    description: "Rotate, manage, and retrieve credentials securely. Eliminates hard-coded secrets.",
    metrics: [
      { label: "Secret storage",      price: "$0.40",  unit: "per secret-month",      detail: "Prorated by the hour" },
      { label: "API calls",           price: "$0.05",  unit: "per 10K API calls",     detail: "GetSecretValue, etc." },
    ],
    free_tier: "30-day trial per secret (new secrets only)",
    pricing_url: "https://aws.amazon.com/secrets-manager/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/SecretsManager",
  },
  {
    service: "KMS",
    key: "kms",
    description: "Key management — create and control encryption keys used by AWS services.",
    metrics: [
      { label: "Customer-managed key", price: "$1.00",  unit: "per key-month",        detail: "AWS-managed keys are free" },
      { label: "API requests",          price: "$0.03",  unit: "per 10K requests",    detail: "Encrypt, Decrypt, etc." },
      { label: "Asymmetric key",        price: "$0.02",  unit: "per 10K operations",  detail: "RSA / ECC" },
    ],
    free_tier: "20K free requests per month",
    pricing_url: "https://aws.amazon.com/kms/pricing/",
    calculator_url: "https://calculator.aws/#/createCalculator/KMS",
  },
];

// ── Try to fetch real Lambda price from AWS Pricing API ───────────────────────
async function fetchLambdaLivePrice(): Promise<{ requests: string; duration: string } | null> {
  try {
    const url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/us-east-1/index.json";
    const r   = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return null;
    const raw  = await r.json() as { products: Record<string, { attributes: Record<string, string> }>; terms: { OnDemand: Record<string, Record<string, { priceDimensions: Record<string, { pricePerUnit: { USD: string }; description: string }> }>> } };
    // Find Lambda request price
    let reqPrice = "", durPrice = "";
    for (const [, terms] of Object.entries(raw.terms.OnDemand)) {
      for (const [, term] of Object.entries(terms)) {
        for (const [, dim] of Object.entries(term.priceDimensions)) {
          if (dim.description.toLowerCase().includes("request")) {
            reqPrice = dim.pricePerUnit.USD;
          }
          if (dim.description.toLowerCase().includes("duration")) {
            durPrice = dim.pricePerUnit.USD;
          }
        }
      }
    }
    if (reqPrice && durPrice) return { requests: reqPrice, duration: durPrice };
  } catch {
    // fall through to curated
  }
  return null;
}

export async function GET() {
  // Return cached data if fresh
  if (_cache && Date.now() - _cache.ts < TTL_MS) {
    return NextResponse.json(_cache.data);
  }

  // Try to get live Lambda price; fall back to curated
  const livePrice = await fetchLambdaLivePrice();

  const services: ServicePrice[] = CURATED.map(s => {
    if (s.key === "lambda" && livePrice) {
      // Patch in live prices for Lambda request/duration
      const patched = { ...s, source: "aws-live" as const };
      patched.metrics = [
        { label: "Requests", price: `$${parseFloat(livePrice.requests) * 1_000_000}`, unit: "per 1M requests", detail: "First 1M/month free" },
        { label: "Duration", price: `$${livePrice.duration}`, unit: "per GB-second", detail: "First 400,000 GB-s/month free" },
        patched.metrics[2],
      ];
      return patched;
    }
    return { ...s, source: "curated" as const };
  });

  const payload: PricingResponse = {
    fetched_at: new Date().toISOString(),
    region:     "us-east-1",
    services,
  };

  _cache = { data: payload, ts: Date.now() };
  return NextResponse.json(payload);
}
