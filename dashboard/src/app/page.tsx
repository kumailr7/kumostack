"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Image from "next/image";
import dynamic from "next/dynamic";

const ArchitectureTab = dynamic(
  () => import("../components/ArchitectureTab"),
  {
    ssr: false,
    loading: () => (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", color: "var(--text-faint)", fontSize: 13 }}>
        Loading diagram…
      </div>
    ),
  }
);

const CDN = "https://icon.icepanel.io/AWS/svg";

interface Service {
  name: string;
  icon: string;
  badge: "free" | "real";
  badgeText?: string;
  healthKey?: string;
  resourceKey?: string; // key into resource counts
}
interface Section { label: string; services: Service[] }

const COLUMNS: Section[][] = [
  [
    {
      label: "App Integration",
      services: [
        { name: "API Gateway",           icon: `${CDN}/App-Integration/API-Gateway.svg`,                  badge: "free", healthKey: "apigateway" },
        { name: "API Gateway v2",        icon: `${CDN}/App-Integration/API-Gateway.svg`,                  badge: "free", healthKey: "apigateway" },
        { name: "SQS",                   icon: `${CDN}/App-Integration/Simple-Queue-Service.svg`,         badge: "free", healthKey: "sqs",    resourceKey: "sqs" },
        { name: "SNS",                   icon: `${CDN}/App-Integration/Simple-Notification-Service.svg`,  badge: "free", healthKey: "sns",    resourceKey: "sns" },
        { name: "Step Functions",        icon: `${CDN}/App-Integration/Step-Functions.svg`,               badge: "free", healthKey: "states", resourceKey: "stepfunctions" },
        { name: "EventBridge",           icon: `${CDN}/App-Integration/EventBridge.svg`,                  badge: "free", healthKey: "events" },
        { name: "EventBridge Scheduler", icon: `${CDN}/App-Integration/EventBridge.svg`,                  badge: "free", healthKey: "scheduler" },
        { name: "AppSync",               icon: `${CDN}/App-Integration/AppSync.svg`,                      badge: "free", healthKey: "appsync" },
        { name: "MQ",                    icon: `${CDN}/App-Integration/MQ.svg`,                           badge: "free", healthKey: "mq" },
      ],
    },
    {
      label: "Compute",
      services: [
        { name: "EC2",          icon: `${CDN}/Compute/EC2.svg`,                                    badge: "free", healthKey: "ec2" },
        { name: "Lambda",       icon: `${CDN}/Compute/Lambda.svg`,                                 badge: "free", healthKey: "lambda", resourceKey: "lambda" },
        { name: "ECS",          icon: `${CDN}/Containers/Elastic-Container-Service.svg`,           badge: "real", badgeText: "Real Docker", healthKey: "ecs" },
        { name: "ECR",          icon: `${CDN}/Containers/Elastic-Container-Registry.svg`,         badge: "free", healthKey: "ecr" },
        { name: "EKS",          icon: `${CDN}/Containers/Elastic-Kubernetes-Service.svg`,         badge: "free", healthKey: "eks" },
        { name: "Batch",        icon: `${CDN}/Compute/Batch.svg`,                                  badge: "free", healthKey: "batch" },
        { name: "Auto Scaling", icon: `${CDN}/Management-Governance/Auto-Scaling.svg`,            badge: "free", healthKey: "autoscaling" },
      ],
    },
  ],
  [
    {
      label: "Management / Governance",
      services: [
        { name: "CloudFormation",          icon: `${CDN}/Management-Governance/CloudFormation.svg`,  badge: "free", healthKey: "cloudformation", resourceKey: "cloudformation" },
        { name: "CloudWatch Logs",         icon: `${CDN}/Management-Governance/CloudWatch.svg`,      badge: "free", healthKey: "logs",  resourceKey: "logs" },
        { name: "CloudWatch",              icon: `${CDN}/Management-Governance/CloudWatch.svg`,      badge: "free", healthKey: "monitoring" },
        { name: "Systems Manager (SSM)",   icon: `${CDN}/Management-Governance/Systems-Manager.svg`, badge: "free", healthKey: "ssm" },
        { name: "Organizations",           icon: `${CDN}/Management-Governance/Organizations.svg`,   badge: "free", healthKey: "organizations" },
        { name: "Account",                 icon: `${CDN}/Management-Governance/Organizations.svg`,   badge: "free", healthKey: "account" },
        { name: "Resource Groups Tagging", icon: `${CDN}/Management-Governance/CloudFormation.svg`,  badge: "free", healthKey: "tagging" },
      ],
    },
    {
      label: "Developer Tools",
      services: [
        { name: "AppConfig", icon: `${CDN}/Management-Governance/AppConfig.svg`, badge: "free", healthKey: "appconfig" },
        { name: "CodeBuild", icon: `${CDN}/Developer-Tools/CodeBuild.svg`,       badge: "free", healthKey: "codebuild" },
      ],
    },
    {
      label: "Business Applications",
      services: [
        { name: "SES",    icon: `${CDN}/Business-Applications/Simple-Email-Service.svg`, badge: "free", healthKey: "ses" },
        { name: "SES v2", icon: `${CDN}/Business-Applications/Simple-Email-Service.svg`, badge: "free", healthKey: "ses" },
      ],
    },
    {
      label: "Front-end Web & Mobile",
      services: [
        { name: "Cognito", icon: `${CDN}/Security-Identity-Compliance/Cognito.svg`, badge: "free", healthKey: "cognito-idp" },
        { name: "AppSync", icon: `${CDN}/App-Integration/AppSync.svg`,              badge: "free", healthKey: "appsync" },
      ],
    },
  ],
  [
    {
      label: "Security, Identity & Compliance",
      services: [
        { name: "IAM",                 icon: `${CDN}/Security-Identity-Compliance/Identity-and-Access-Management.svg`, badge: "free", healthKey: "iam" },
        { name: "STS",                 icon: `${CDN}/Security-Identity-Compliance/Identity-and-Access-Management.svg`, badge: "free", healthKey: "sts" },
        { name: "Secrets Manager",     icon: `${CDN}/Security-Identity-Compliance/Secrets-Manager.svg`,                badge: "free", healthKey: "secretsmanager", resourceKey: "secretsmanager" },
        { name: "KMS",                 icon: `${CDN}/Security-Identity-Compliance/Key-Management-Service.svg`,         badge: "free", healthKey: "kms" },
        { name: "Certificate Manager", icon: `${CDN}/Security-Identity-Compliance/Certificate-Manager.svg`,            badge: "free", healthKey: "acm" },
        { name: "WAF v2",              icon: `${CDN}/Security-Identity-Compliance/WAF.svg`,                            badge: "free", healthKey: "wafv2" },
      ],
    },
    {
      label: "Storage",
      services: [
        { name: "S3",       icon: `${CDN}/Storage/Simple-Storage-Service.svg`, badge: "free", healthKey: "s3",              resourceKey: "s3" },
        { name: "S3 Files", icon: `${CDN}/Storage/Simple-Storage-Service.svg`, badge: "free", healthKey: "s3files" },
        { name: "EBS",      icon: `${CDN}/Storage/Elastic-Block-Store.svg`,    badge: "free", healthKey: "ec2" },
        { name: "EFS",      icon: `${CDN}/Storage/EFS.svg`,                    badge: "free", healthKey: "elasticfilesystem" },
        { name: "Backup",   icon: `${CDN}/Storage/Backup.svg`,                 badge: "free", healthKey: "backup" },
      ],
    },
    {
      label: "Networking",
      services: [
        { name: "Route 53",        icon: `${CDN}/Networking-Content-Delivery/Route-53.svg`,               badge: "free", healthKey: "route53" },
        { name: "CloudFront",      icon: `${CDN}/Networking-Content-Delivery/CloudFront.svg`,             badge: "free", healthKey: "cloudfront" },
        { name: "ALB / ELBv2",     icon: `${CDN}/Networking-Content-Delivery/Elastic-Load-Balancing.svg`, badge: "free", healthKey: "elasticloadbalancing" },
        { name: "Cloud Map",       icon: `${CDN}/Networking-Content-Delivery/Cloud-Map.svg`,              badge: "free", healthKey: "servicediscovery" },
        { name: "Transfer Family", icon: `${CDN}/Migration-Transfer/Transfer-Family.svg`,                 badge: "free", healthKey: "transfer" },
      ],
    },
    {
      label: "Machine Learning",
      services: [
        { name: "Bedrock (mock)", icon: `${CDN}/Machine-Learning/Bedrock.svg`, badge: "free", healthKey: "bedrock" },
      ],
    },
  ],
  [
    {
      label: "Database",
      services: [
        { name: "DynamoDB",     icon: `${CDN}/Database/DynamoDB.svg`,            badge: "free", healthKey: "dynamodb",      resourceKey: "dynamodb" },
        { name: "RDS",          icon: `${CDN}/Database/RDS.svg`,                 badge: "real", badgeText: "Real Docker", healthKey: "rds" },
        { name: "RDS Data API", icon: `${CDN}/Database/RDS.svg`,                 badge: "free", healthKey: "rds-data" },
        { name: "ElastiCache",  icon: `${CDN}/Database/ElastiCache.svg`,         badge: "real", badgeText: "Real Docker", healthKey: "elasticache" },
        { name: "OpenSearch",   icon: `${CDN}/Analytics/OpenSearch-Service.svg`, badge: "real", badgeText: "Real Docker", healthKey: "opensearch" },
      ],
    },
    {
      label: "Analytics",
      services: [
        { name: "Athena",        icon: `${CDN}/Analytics/Athena.svg`,           badge: "real", badgeText: "DuckDB", healthKey: "athena" },
        { name: "Glue",          icon: `${CDN}/Analytics/Glue.svg`,             badge: "free", healthKey: "glue" },
        { name: "EMR",           icon: `${CDN}/Analytics/EMR.svg`,              badge: "free", healthKey: "elasticmapreduce" },
        { name: "Kinesis",       icon: `${CDN}/Analytics/Kinesis.svg`,          badge: "free", healthKey: "kinesis", resourceKey: "kinesis" },
        { name: "Data Firehose", icon: `${CDN}/Analytics/Kinesis-Firehose.svg`, badge: "free", healthKey: "firehose" },
      ],
    },
    {
      label: "Internal / Metadata",
      services: [
        { name: "IMDS (v1 + v2)", icon: `${CDN}/Compute/EC2.svg`,                     badge: "free", healthKey: "imds" },
        { name: "WAF Classic",    icon: `${CDN}/Security-Identity-Compliance/WAF.svg`, badge: "free", healthKey: "waf-regional" },
      ],
    },
  ],
];

const NAV_ITEMS = [
  { id: "Overview",         label: "Overview",         icon: <IconGrid /> },
  { id: "Organizations",    label: "Organizations",    icon: <IconOrg />, highlight: true },
  { id: "Stackport",        label: "Resource Browser", icon: <IconStackport /> },
  { id: "Diagrams",         label: "Diagrams",         icon: <IconDrawio /> },
  { id: "Tutorials",        label: "Tutorials",        icon: <IconBook /> },
  { id: "Extensions",       label: "Extensions",       icon: <IconPuzzle /> },
  { id: "Architecture",     label: "Architecture",     icon: <IconDiagram /> },
  { id: "Status",           label: "Service Status",   icon: <IconStatus /> },
  { id: "State",            label: "State",            icon: <IconDatabase /> },
  { id: "App Inspector",    label: "App Inspector",    icon: <IconInspect /> },
  { id: "Logs",             label: "Logs",             icon: <IconTerminal /> },
];

const REGIONS = ["us-east-1","us-east-2","us-west-1","us-west-2","eu-west-1","eu-central-1","ap-southeast-1"];

type ServiceStatus    = Record<string, string>;
type ResourceCounts   = Record<string, number>;

// ─── Multi-Account / Organizations Types ──────────────────────────────────────

type AccountStatus = "ACTIVE" | "SUSPENDED";
type AccountType   = "MANAGEMENT" | "MEMBER";

interface Account {
  id:     string;
  name:   string;
  email:  string;
  status: AccountStatus;
  region: string;
  ouId:   string | null;
  type:   AccountType;
  color:  string;
}

interface OrgUnit {
  id:       string;
  name:     string;
  parentId: string | null;
}

interface SCP {
  id:          string;
  name:        string;
  description: string;
  effect:      "ALLOW" | "DENY";
  services:    string[];
  attachedTo:  string[];
  status:      "ENABLED" | "DISABLED";
}

const MOCK_OUS: OrgUnit[] = [
  { id: "r-0001",  name: "Root",          parentId: null      },
  { id: "ou-eng",  name: "Engineering",   parentId: "r-0001"  },
  { id: "ou-data", name: "Data Platform", parentId: "r-0001"  },
  { id: "ou-prod", name: "Production",    parentId: "r-0001"  },
];

const MOCK_ACCOUNTS: Account[] = [
  { id: "000000000000", name: "management",   email: "root@kumostack.local",    status: "ACTIVE", region: "us-east-1", ouId: "r-0001",  type: "MANAGEMENT", color: "#10b981" },
  { id: "111111111111", name: "dev-team",     email: "dev@kumostack.local",     status: "ACTIVE", region: "us-east-1", ouId: "ou-eng",  type: "MEMBER",     color: "#3b82f6" },
  { id: "222222222222", name: "staging",      email: "staging@kumostack.local", status: "ACTIVE", region: "us-east-1", ouId: "ou-eng",  type: "MEMBER",     color: "#f59e0b" },
  { id: "333333333333", name: "production",   email: "prod@kumostack.local",    status: "ACTIVE", region: "us-east-2", ouId: "ou-prod", type: "MEMBER",     color: "#ef4444" },
  { id: "444444444444", name: "data-pipeline",email: "data@kumostack.local",    status: "ACTIVE", region: "us-west-2", ouId: "ou-data", type: "MEMBER",     color: "#8b5cf6" },
];

const MOCK_SCPS: SCP[] = [
  { id: "scp-001", name: "DenyS3BucketDelete",  description: "Prevent S3 bucket deletion in production",      effect: "DENY",  services: ["S3"],     attachedTo: ["ou-prod"],              status: "ENABLED"  },
  { id: "scp-002", name: "RequireRegionLock",    description: "Restrict to us-east-1 and us-east-2 only",     effect: "DENY",  services: ["*"],      attachedTo: ["r-0001"],               status: "ENABLED"  },
  { id: "scp-003", name: "DenyRootUser",         description: "Deny all actions performed by the root user",  effect: "DENY",  services: ["*"],      attachedTo: ["r-0001"],               status: "ENABLED"  },
  { id: "scp-004", name: "AllowLambdaFullDev",   description: "Allow full Lambda access in Engineering OU",   effect: "ALLOW", services: ["Lambda"], attachedTo: ["ou-eng"],               status: "ENABLED"  },
  { id: "scp-005", name: "DenyIAMUserCreate",    description: "Enforce federation — no long-term IAM users",  effect: "DENY",  services: ["IAM"],    attachedTo: ["ou-prod", "ou-data"],   status: "DISABLED" },
];

// ─── Icons ────────────────────────────────────────────────────────────────────

function IconStackport(){ return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 20h20M6 20V10l6-6 6 6v10M10 20v-5h4v5"/></svg>; }
function IconDrawio()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/><circle cx="15" cy="15" r="2"/></svg>; }
function IconBook()     { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>; }
function IconGrid()     { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>; }
function IconPuzzle()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>; }
function IconDiagram()  { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="6" height="4" rx="1"/><rect x="16" y="3" width="6" height="4" rx="1"/><rect x="9" y="17" width="6" height="4" rx="1"/><path d="M5 7v4h14V7M12 11v6"/></svg>; }
function IconStatus()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>; }
function IconSearch()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function IconDatabase() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>; }
function IconInspect()  { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>; }
function IconTerminal() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>; }
function IconChevron({ open }: { open: boolean }) {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: open ? "rotate(0deg)" : "rotate(180deg)", transition: "transform 0.2s" }}><polyline points="15 18 9 12 15 6"/></svg>;
}
function IconOrg() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="2" width="8" height="4" rx="1"/><rect x="1" y="17" width="6" height="4" rx="1"/><rect x="9" y="17" width="6" height="4" rx="1"/><rect x="17" y="17" width="6" height="4" rx="1"/><path d="M4 17v-3a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v3M12 6v7"/></svg>; }

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusDotClass(status: string | undefined) {
  if (!status) return "";
  if (status === "available" || status === "running") return "svc-dot svc-dot--up";
  if (status === "error") return "svc-dot svc-dot--err";
  return "svc-dot svc-dot--idle";
}

function StatusPill({ status }: { status: string | undefined }) {
  if (!status) return <span className="pill pill--dim">Unknown</span>;
  if (status === "available" || status === "running") return <span className="pill pill--green">Running</span>;
  if (status === "error") return <span className="pill pill--red">Error</span>;
  return <span className="pill pill--dim">{status}</span>;
}

function WarnIcon() {
  return (
    <svg className="notice-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function DisconnectedNotice() {
  return (
    <div className="notice">
      <WarnIcon />
      <div>
        KumoStack is not connected. Run{" "}
        <span className="mono" style={{ background: "rgba(0,0,0,0.3)", padding: "1px 6px", borderRadius: 3 }}>
          docker run -p 4566:4566 kumostackorg/kumostack
        </span>{" "}
        to start it.
      </div>
    </div>
  );
}

// ─── Tutorials Tab ────────────────────────────────────────────────────────────

interface Tutorial {
  title: string;
  url: string;
  description: string;
  services: string[];
  difficulty: "Beginner" | "Intermediate" | "Advanced";
  time: string;
  tags: string[];
}

const DOCS_BASE = "https://kumailr7.github.io/ministack";

const TUTORIALS: Tutorial[] = [
  {
    title: "Getting Started with KumoStack",
    url: `${DOCS_BASE}/tutorials/getting-started/`,
    description: "Spin up the stack, create your first S3 bucket, deploy a Lambda, and send your first SQS message — all without an AWS account.",
    services: ["S3", "Lambda", "SQS"],
    difficulty: "Beginner",
    time: "15 min",
    tags: ["Quick Start", "CLI"],
  },
  {
    title: "S3 — Object Storage",
    url: `${DOCS_BASE}/tutorials/s3/`,
    description: "Buckets, versioning, lifecycle policies, static website hosting, event notifications, and presigned URLs.",
    services: ["S3"],
    difficulty: "Beginner",
    time: "20 min",
    tags: ["Storage", "Lifecycle", "Events"],
  },
  {
    title: "Lambda — Serverless Functions",
    url: `${DOCS_BASE}/tutorials/lambda/`,
    description: "Deploy Python Lambdas, set environment variables, trigger from SQS, use layers, and run container-image functions.",
    services: ["Lambda", "SQS", "ECR"],
    difficulty: "Intermediate",
    time: "25 min",
    tags: ["Serverless", "Python", "Docker"],
  },
  {
    title: "RDS — Managed Databases",
    url: `${DOCS_BASE}/tutorials/rds/`,
    description: "Launch a PostgreSQL or MySQL instance, connect via psql, store credentials in Secrets Manager, and monitor in Grafana.",
    services: ["RDS", "Secrets Manager"],
    difficulty: "Intermediate",
    time: "20 min",
    tags: ["PostgreSQL", "MySQL", "Secrets"],
  },
  {
    title: "DynamoDB — NoSQL Tables",
    url: `${DOCS_BASE}/tutorials/dynamodb/`,
    description: "Create tables with GSIs, perform CRUD operations, enable DynamoDB Streams, and run batch writes.",
    services: ["DynamoDB"],
    difficulty: "Beginner",
    time: "15 min",
    tags: ["NoSQL", "Streams", "GSI"],
  },
  {
    title: "SQS & SNS — Messaging",
    url: `${DOCS_BASE}/tutorials/sqs-sns/`,
    description: "Create standard and FIFO queues, dead-letter queues, SNS fan-out to multiple queues, and Lambda subscriptions.",
    services: ["SQS", "SNS", "Lambda"],
    difficulty: "Beginner",
    time: "20 min",
    tags: ["Messaging", "Fan-out", "DLQ"],
  },
  {
    title: "API Gateway — REST & HTTP APIs",
    url: `${DOCS_BASE}/tutorials/api-gateway/`,
    description: "Create REST APIs backed by Lambda, deploy stages, and use the simpler HTTP API v2 in a single command.",
    services: ["API Gateway", "Lambda", "IAM"],
    difficulty: "Intermediate",
    time: "25 min",
    tags: ["REST", "HTTP API", "Lambda Proxy"],
  },
  {
    title: "Grafana Monitoring",
    url: `${DOCS_BASE}/guides/grafana/`,
    description: "Connect Grafana to KumoStack's CloudWatch emulation, push custom metrics, and explore 20+ pre-built AWS dashboards.",
    services: ["CloudWatch"],
    difficulty: "Intermediate",
    time: "20 min",
    tags: ["Grafana", "Dashboards", "CloudWatch"],
  },
  {
    title: "Vector.dev Log Archiving",
    url: `${DOCS_BASE}/guides/vector-logging/`,
    description: "3-tier log pipeline: live queries in Loki, hot archive in KumoStack S3, cold archive in Garage with lifecycle policies.",
    services: ["S3"],
    difficulty: "Intermediate",
    time: "30 min",
    tags: ["Logs", "Loki", "Garage", "Vector"],
  },
  {
    title: "draw.io Architecture Diagrams",
    url: `${DOCS_BASE}/guides/drawio/`,
    description: "Design AWS architecture diagrams with official AWS shapes in the embedded draw.io editor, then export or commit to your repo.",
    services: [],
    difficulty: "Beginner",
    time: "10 min",
    tags: ["Diagrams", "Architecture", "draw.io"],
  },
  {
    title: "awslocal TUI — Auto-add to Grafana",
    url: `${DOCS_BASE}/guides/awslocal-tui/`,
    description: "Use the awslocal wrapper to get a TUI prompt after every resource creation offering to wire it straight into a Grafana dashboard.",
    services: ["Lambda", "SQS", "DynamoDB", "S3"],
    difficulty: "Beginner",
    time: "10 min",
    tags: ["TUI", "Grafana", "Automation"],
  },
  {
    title: "Stackport Resource Browser",
    url: `${DOCS_BASE}/guides/stackport/`,
    description: "Full CRUD browser for every AWS resource — create, inspect, and delete without touching the CLI.",
    services: ["S3", "Lambda", "SQS", "DynamoDB", "RDS"],
    difficulty: "Beginner",
    time: "10 min",
    tags: ["UI", "CRUD", "Browse"],
  },
  {
    title: "Terraform & tfstack",
    url: `${DOCS_BASE}/tutorials/terraform/`,
    description: "Provision KumoStack resources with Terraform using tfstack — no config needed. State stored durably in Garage S3.",
    services: ["S3", "SQS", "Lambda", "DynamoDB"],
    difficulty: "Intermediate",
    time: "20 min",
    tags: ["Terraform", "IaC", "Garage", "State"],
  },
  {
    title: "Garage — Durable Local S3",
    url: `${DOCS_BASE}/guides/garage/`,
    description: "Use Garage as a persistent S3-compatible store for Terraform state, log archives, and any data that must survive KumoStack restarts.",
    services: ["S3"],
    difficulty: "Beginner",
    time: "10 min",
    tags: ["Garage", "S3", "Terraform", "Persistence"],
  },
];

const DIFFICULTY_COLOR: Record<string, string> = {
  Beginner:     "#10b981",
  Intermediate: "#f59e0b",
  Advanced:     "#ef4444",
};

const SERVICE_COLOR: Record<string, string> = {
  Lambda: "#E7157B", DynamoDB: "#527FFF", S3: "#3F8624",
  "API Gateway": "#8C4FFF", SQS: "#E7157B", SNS: "#E7157B",
  ECS: "#F58536", ECR: "#F58536", IAM: "#DD344C", RDS: "#527FFF",
  CloudFront: "#8C4FFF", CloudFormation: "#E7157B", ELB: "#8C4FFF",
  Route53: "#8C4FFF", SES: "#E7157B", Glue: "#8C4FFF", MSK: "#F58536",
  "Step Functions": "#E7157B", Cognito: "#DD344C",
};

function TutorialsTab() {
  const [search,     setSearch]     = useState("");
  const [diffFilter, setDiffFilter] = useState<string>("All");
  const [svcFilter,  setSvcFilter]  = useState<string>("All");

  const allServices = [...new Set(TUTORIALS.flatMap((t) => t.services))].sort();

  const visible = TUTORIALS.filter((t) => {
    const q = search.trim().toLowerCase();
    const matchSearch = !q ||
      t.title.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.services.some((s) => s.toLowerCase().includes(q)) ||
      t.tags.some((s) => s.toLowerCase().includes(q));
    const matchDiff = diffFilter === "All" || t.difficulty === diffFilter;
    const matchSvc  = svcFilter  === "All" || t.services.includes(svcFilter);
    return matchSearch && matchDiff && matchSvc;
  });

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Tutorials</h1>
          <p className="page-subtitle">
            {TUTORIALS.length} hands-on guides — built for KumoStack ·{" "}
            <a href={DOCS_BASE} target="_blank" rel="noreferrer"
               style={{ color: "var(--accent)", textDecoration: "none" }}>
              kumailr7.github.io/ministack ↗
            </a>
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{visible.length} shown</span>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
        <input
          className="search"
          style={{ flex: 1, minWidth: 200, maxWidth: 360, marginBottom: 0, padding: "8px 14px", fontSize: 13 }}
          placeholder="Search tutorials, services, tags…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filter-pills">
          {["All", "Beginner", "Intermediate", "Advanced"].map((d) => (
            <button key={d} className={`pill-btn ${diffFilter === d ? "active" : ""}`}
              onClick={() => setDiffFilter(d)}
              style={diffFilter === d && d !== "All" ? { borderColor: DIFFICULTY_COLOR[d], color: DIFFICULTY_COLOR[d] } : {}}>
              {d}
            </button>
          ))}
        </div>
        <select
          value={svcFilter}
          onChange={(e) => setSvcFilter(e.target.value)}
          style={{ background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: "var(--radius-sm)", padding: "6px 28px 6px 10px", color: "var(--text)", fontSize: 12, fontFamily: "inherit", appearance: "none", backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239aa1ad' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>\")", backgroundRepeat: "no-repeat", backgroundPosition: "right 8px center" }}>
          <option value="All">All services</option>
          {allServices.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 28 }}>
        {[
          { label: "Total Tutorials",   value: TUTORIALS.length,                              color: "#60a5fa" },
          { label: "Beginner",          value: TUTORIALS.filter(t=>t.difficulty==="Beginner").length,     color: "#10b981" },
          { label: "Intermediate",      value: TUTORIALS.filter(t=>t.difficulty==="Intermediate").length, color: "#f59e0b" },
          { label: "Advanced",          value: TUTORIALS.filter(t=>t.difficulty==="Advanced").length,     color: "#ef4444" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: "var(--bg-card)", border: `1px solid ${color}25`, borderRadius: "var(--radius)", padding: "14px 18px", display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ fontSize: 28, fontWeight: 700, color, letterSpacing: "-0.03em", lineHeight: 1 }}>{value}</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.07em" }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Tutorial cards grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 16 }}>
        {visible.map((t) => (
          <a key={t.url} href={t.url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
            <div className="tutorial-card">
              {/* Card header */}
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text)", lineHeight: 1.4, margin: 0, flex: 1 }}>
                  {t.title}
                </h3>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </div>

              {/* Description */}
              <p style={{ fontSize: 12, color: "var(--text-dim)", lineHeight: 1.6, margin: "0 0 12px" }}>
                {t.description}
              </p>

              {/* Services */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 12 }}>
                {t.services.map((s) => (
                  <span key={s} style={{
                    fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 4,
                    background: `${SERVICE_COLOR[s] ?? "#6b7280"}18`,
                    border: `1px solid ${SERVICE_COLOR[s] ?? "#6b7280"}35`,
                    color: SERVICE_COLOR[s] ?? "var(--text-dim)",
                  }}>{s}</span>
                ))}
              </div>

              {/* Footer: difficulty + time + tags */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 10, borderTop: "1px solid var(--border)", flexWrap: "wrap" }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 999,
                  background: `${DIFFICULTY_COLOR[t.difficulty]}18`,
                  border: `1px solid ${DIFFICULTY_COLOR[t.difficulty]}40`,
                  color: DIFFICULTY_COLOR[t.difficulty],
                }}>{t.difficulty}</span>

                <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--text-faint)" }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  {t.time}
                </span>

                <div style={{ marginLeft: "auto", display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {t.tags.slice(0, 2).map((tag) => (
                    <span key={tag} style={{ fontSize: 10, color: "var(--text-faint)", background: "var(--bg-elevated)", padding: "1px 6px", borderRadius: 3, border: "1px solid var(--border)" }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </a>
        ))}
      </div>

      {visible.length === 0 && (
        <div className="empty-state">No tutorials match your search.</div>
      )}

      {/* Footer note */}
      <div style={{ marginTop: 40, padding: "16px 20px", background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--text-dim)", lineHeight: 1.7 }}>
        <strong style={{ color: "var(--text)" }}>Tip:</strong> All tutorials target KumoStack at{" "}
        <code className="inline-code">localhost:4566</code>. Use{" "}
        <code className="inline-code">awslocal</code> or set{" "}
        <code className="inline-code">AWS_ENDPOINT_URL=http://localhost:4566</code> — no real AWS credentials needed.{" "}
        <a href={DOCS_BASE} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", textDecoration: "none" }}>
          Browse the full docs site ↗
        </a>
      </div>
    </div>
  );
}

// ─── Diagrams Tab (draw.io) ───────────────────────────────────────────────────

// Starter KumoStack architecture diagram encoded as draw.io XML
const KUMOSTACK_TEMPLATE_XML = encodeURIComponent(`
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>

    <!-- Title -->
    <mxCell id="t1" value="KumoStack Local AWS Architecture" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=18;fontStyle=1;fontColor=#10b981;" vertex="1" parent="1">
      <mxGeometry x="200" y="20" width="500" height="40" as="geometry"/>
    </mxCell>

    <!-- Client -->
    <mxCell id="c1" value="Developer / Client" style="shape=mxgraph.aws4.user;fillColor=#232F3E;strokeColor=#ffffff;fontColor=#ffffff;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="380" y="90" width="60" height="70" as="geometry"/>
    </mxCell>

    <!-- Gateway -->
    <mxCell id="g1" value="KumoStack Gateway&#xa;localhost:4566" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#232F3E;strokeColor=#10b981;fontColor=#10b981;fontSize=11;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="330" y="210" width="160" height="50" as="geometry"/>
    </mxCell>

    <!-- S3 -->
    <mxCell id="s3" value="S3&#xa;(Object Storage)" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.s3;fillColor=#3F8624;strokeColor=#ffffff;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="80" y="330" width="70" height="70" as="geometry"/>
    </mxCell>

    <!-- Lambda -->
    <mxCell id="lb" value="Lambda&#xa;(Functions)" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambda;fillColor=#E7157B;strokeColor=#ffffff;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="200" y="330" width="70" height="70" as="geometry"/>
    </mxCell>

    <!-- DynamoDB -->
    <mxCell id="db" value="DynamoDB&#xa;(Tables)" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.dynamodb;fillColor=#527FFF;strokeColor=#ffffff;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="320" y="330" width="70" height="70" as="geometry"/>
    </mxCell>

    <!-- SQS -->
    <mxCell id="sq" value="SQS&#xa;(Queues)" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.sqs;fillColor=#E7157B;strokeColor=#ffffff;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="440" y="330" width="70" height="70" as="geometry"/>
    </mxCell>

    <!-- RDS -->
    <mxCell id="rd" value="RDS&#xa;(PostgreSQL 15)" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.rds;fillColor=#527FFF;strokeColor=#ffffff;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="560" y="330" width="70" height="70" as="geometry"/>
    </mxCell>

    <!-- Redis -->
    <mxCell id="rc" value="Redis&#xa;(Cache)" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.elasticache;fillColor=#527FFF;strokeColor=#ffffff;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="680" y="330" width="70" height="70" as="geometry"/>
    </mxCell>

    <!-- Observability Stack -->
    <mxCell id="obs" value="Observability Stack" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1a1f2e;strokeColor=#2e3645;fontColor=#9aa1ad;fontSize=11;fontStyle=2;dashed=1;" vertex="1" parent="1">
      <mxGeometry x="60" y="470" width="660" height="40" as="geometry"/>
    </mxCell>

    <!-- Prometheus -->
    <mxCell id="pr" value="Prometheus&#xa;:9091" style="ellipse;whiteSpace=wrap;html=1;fillColor=#e65100;strokeColor=#FF6D00;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="80" y="530" width="90" height="50" as="geometry"/>
    </mxCell>

    <!-- Loki -->
    <mxCell id="lk" value="Loki&#xa;:3100" style="ellipse;whiteSpace=wrap;html=1;fillColor=#F46800;strokeColor=#F46800;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="200" y="530" width="90" height="50" as="geometry"/>
    </mxCell>

    <!-- Vector -->
    <mxCell id="ve" value="Vector.dev&#xa;:8686" style="ellipse;whiteSpace=wrap;html=1;fillColor=#10b981;strokeColor=#10b981;fontColor=#000000;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="320" y="530" width="90" height="50" as="geometry"/>
    </mxCell>

    <!-- Grafana -->
    <mxCell id="gr" value="Grafana&#xa;:3002" style="ellipse;whiteSpace=wrap;html=1;fillColor=#F46800;strokeColor=#F46800;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="440" y="530" width="90" height="50" as="geometry"/>
    </mxCell>

    <!-- Garage -->
    <mxCell id="ga" value="Garage&#xa;S3 Cold Archive&#xa;:3900" style="ellipse;whiteSpace=wrap;html=1;fillColor=#2563eb;strokeColor=#3b82f6;fontColor=#ffffff;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="560" y="530" width="100" height="50" as="geometry"/>
    </mxCell>

    <!-- Edges -->
    <mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#10b981;" edge="1" source="c1" target="g1" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e2" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#9aa1ad;" edge="1" source="g1" target="s3" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e3" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#9aa1ad;" edge="1" source="g1" target="lb" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e4" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#9aa1ad;" edge="1" source="g1" target="db" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e5" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#9aa1ad;" edge="1" source="g1" target="sq" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e6" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#9aa1ad;" edge="1" source="g1" target="rd" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e7" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#527FFF;" edge="1" source="g1" target="rc" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e8" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#F46800;dashed=1;" edge="1" source="ve" target="lk" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e9" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#F46800;dashed=1;" edge="1" source="lk" target="gr" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e10" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#2563eb;dashed=1;" edge="1" source="ve" target="ga" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="e11" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#e65100;dashed=1;" edge="1" source="pr" target="gr" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
  </root>
</mxGraphModel>
`);

const DRAWIO_URL = "http://localhost:8083";

function DiagramsTab() {
  const [health, setHealth]     = useState<"loading" | "ok" | "error">("loading");
  const [mode, setMode]         = useState<"editor" | "template">("editor");
  const [templateLoaded, setTemplateLoaded] = useState(false);

  useEffect(() => {
    // Health check goes through the Next.js API proxy to avoid browser CORS issues
    fetch("/api/drawio", { signal: AbortSignal.timeout(5000) })
      .then((r) => setHealth(r.ok ? "ok" : "error"))
      .catch(() => setHealth("error"));
  }, []);

  // Build draw.io URL with template pre-loaded
  const editorUrl  = `${DRAWIO_URL}/?embed=1&ui=dark&spin=1&proto=json&libraries=1`;
  const templateUrl = `${DRAWIO_URL}/?embed=1&ui=dark&spin=1&xml=${KUMOSTACK_TEMPLATE_XML}&title=KumoStack%20Architecture`;

  return (
    <div className="fullscreen-tab">
      {/* Header */}
      <div className="fullscreen-tab-bar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/><circle cx="15" cy="15" r="2"/>
          </svg>
          <span style={{ fontWeight: 700, fontSize: 14 }}>draw.io</span>
          <span style={{ fontSize: 11, color: "var(--text-faint)" }}>— Architecture Diagrams</span>
        </div>
        <span className={`pill ${health === "ok" ? "pill--green" : health === "error" ? "pill--red" : "pill--dim"}`} style={{ fontSize: 10 }}>
          {health === "ok" ? "Running" : health === "error" ? "Starting…" : "Checking…"}
        </span>

        {health === "ok" && (
          <div className="filter-pills" style={{ marginLeft: 8 }}>
            <button className={`pill-btn ${mode === "editor" ? "active" : ""}`} onClick={() => setMode("editor")}>Blank Canvas</button>
            <button className={`pill-btn ${mode === "template" ? "active" : ""}`} onClick={() => { setMode("template"); setTemplateLoaded(true); }}>
              KumoStack Template
            </button>
          </div>
        )}

        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <a href={DRAWIO_URL} target="_blank" rel="noreferrer" className="btn btn-sm">Open in new tab ↗</a>
          {mode === "template" && (
            <a href={templateUrl} target="_blank" rel="noreferrer" className="btn btn-sm btn-primary">Open Template ↗</a>
          )}
        </div>
      </div>

      {/* Content */}
      {health === "error" ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
          <div style={{
            background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: 12,
            padding: "40px 48px", textAlign: "center", maxWidth: 440,
          }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1" style={{ margin: "0 auto 16px", display: "block" }}>
              <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
            </svg>
            <p style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>draw.io is starting</p>
            <p style={{ color: "var(--text-faint)", fontSize: 13, lineHeight: 1.6, marginBottom: 20 }}>
              The draw.io container is initialising. Usually ready in 10–15 seconds.
            </p>
            <div className="code-snippet" style={{ textAlign: "left", marginBottom: 16 }}>docker compose up -d drawio</div>
            <button className="btn btn-sm btn-primary" onClick={() => {
              setHealth("loading");
              fetch("/api/drawio", { signal: AbortSignal.timeout(5000) })
                .then((r) => setHealth(r.ok ? "ok" : "error"))
                .catch(() => setHealth("error"));
            }}>Check again</button>
          </div>
        </div>
      ) : (
        <iframe
          key={mode}
          src={mode === "template" && templateLoaded ? templateUrl : editorUrl}
          className="fullscreen-iframe"
          title="draw.io Architecture Editor"
          allow="clipboard-read; clipboard-write"
        />
      )}
    </div>
  );
}

// ─── Stackport Tab ────────────────────────────────────────────────────────────

function StackportTab() {
  const STACKPORT_URL = "http://localhost:8082";
  const [health, setHealth] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    fetch(`${STACKPORT_URL}/api/health`, { signal: AbortSignal.timeout(3000) })
      .then((r) => setHealth(r.ok ? "ok" : "error"))
      .catch(() => setHealth("error"));
  }, []);

  return (
    <div className="fullscreen-tab">
      {/* Header bar */}
      <div className="fullscreen-tab-bar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 20h20M6 20V10l6-6 6 6v10M10 20v-5h4v5"/>
          </svg>
          <span style={{ fontWeight: 700, fontSize: 14 }}>Stackport</span>
          <span style={{ fontSize: 11, color: "var(--text-faint)" }}>— AWS Resource Browser</span>
        </div>
        <span className={`pill ${health === "ok" ? "pill--green" : health === "error" ? "pill--red" : "pill--dim"}`} style={{ fontSize: 10 }}>
          {health === "ok" ? "Running" : health === "error" ? "Starting…" : "Checking…"}
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <a href={STACKPORT_URL} target="_blank" rel="noreferrer" className="btn btn-sm">Open in new tab ↗</a>
        </div>
      </div>

      {/* Iframe or not-ready state */}
      {health === "error" ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
          <div style={{
            background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: 12,
            padding: "40px 48px", textAlign: "center", maxWidth: 440,
          }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1" style={{ margin: "0 auto 16px", display: "block" }}>
              <path d="M2 20h20M6 20V10l6-6 6 6v10M10 20v-5h4v5"/>
            </svg>
            <p style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>Stackport is starting</p>
            <p style={{ color: "var(--text-faint)", fontSize: 13, lineHeight: 1.6, marginBottom: 20 }}>
              The Stackport container is still initialising. This usually takes 10–20 seconds on first start.
            </p>
            <div className="code-snippet" style={{ textAlign: "left", marginBottom: 16 }}>docker compose up -d stackport</div>
            <button className="btn btn-sm btn-primary" onClick={() => { setHealth("loading"); fetch(`${STACKPORT_URL}/api/health`, { signal: AbortSignal.timeout(3000) }).then((r) => setHealth(r.ok ? "ok" : "error")).catch(() => setHealth("error")); }}>
              Check again
            </button>
          </div>
        </div>
      ) : (
        <iframe
          src={STACKPORT_URL}
          className="fullscreen-iframe"
          title="Stackport Resource Browser"
          allow="clipboard-write"
        />
      )}
    </div>
  );
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

function Sidebar({ activeTab, setTab, connected, version, collapsed, setCollapsed, activeAccount, setActiveAccount }: {
  activeTab: string;
  setTab: (t: string) => void;
  connected: boolean;
  version: string | null;
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  activeAccount: Account;
  setActiveAccount: (a: Account) => void;
}) {
  const [showAccounts, setShowAccounts] = useState(false);

  return (
    <aside className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`}>
      {/* Logo row */}
      <div className="sidebar-logo">
        {!collapsed && (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <img src="/Kumostack_logo.png" alt="KumoStack" width="26" height="26" />
            <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em" }}>KumoStack</span>
          </div>
        )}
        {collapsed && (
          <img src="/Kumostack_logo.png" alt="KumoStack" width="26" height="26" />
        )}
        <button className="sidebar-collapse-btn" onClick={() => setCollapsed(!collapsed)} title={collapsed ? "Expand" : "Collapse"}>
          <IconChevron open={!collapsed} />
        </button>
      </div>

      {/* Account switcher */}
      <div className="sidebar-account" style={{ position: "relative" }}>
        <button
          className="sidebar-account-btn"
          onClick={() => setShowAccounts(!showAccounts)}
          title={collapsed ? activeAccount.name : undefined}
        >
          <span className="acct-dot" style={{ background: activeAccount.color }} />
          {!collapsed && (
            <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {activeAccount.name}
              </div>
              <div style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "var(--font-mono, monospace)" }}>
                {activeAccount.id} · {activeAccount.region}
              </div>
            </div>
          )}
          {!collapsed && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>}
        </button>

        {/* Account dropdown */}
        {showAccounts && !collapsed && (
          <div className="acct-dropdown">
            <div className="acct-dropdown-header">SWITCH ACCOUNT</div>
            {MOCK_ACCOUNTS.map((a) => (
              <button
                key={a.id}
                className={`acct-option${a.id === activeAccount.id ? " acct-option--active" : ""}`}
                onClick={() => { setActiveAccount(a); setShowAccounts(false); }}
              >
                <span className="acct-dot" style={{ background: a.color }} />
                <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.name}</div>
                  <div style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "var(--font-mono, monospace)" }}>{a.id}</div>
                </div>
                {a.type === "MANAGEMENT" && <span style={{ fontSize: 9, fontWeight: 700, padding: "1px 5px", background: "rgba(16,185,129,0.15)", color: "var(--accent)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 3, flexShrink: 0 }}>ROOT</span>}
                {a.id === activeAccount.id && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>}
              </button>
            ))}
            <button className="acct-option acct-option--add" onClick={() => { setShowAccounts(false); setTab("Organizations"); }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              <span style={{ fontSize: 12, color: "var(--text-dim)" }}>Manage accounts</span>
            </button>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sidebar-item${activeTab === item.id ? " sidebar-item--active" : ""}${"highlight" in item && item.highlight ? " sidebar-item--highlight" : ""}`}
            onClick={() => { setTab(item.id); setShowAccounts(false); }}
            title={collapsed ? item.label : undefined}
          >
            <span className="sidebar-item-icon">{item.icon}</span>
            {!collapsed && <span className="sidebar-item-label">{item.label}</span>}
            {!collapsed && "highlight" in item && item.highlight && (
              <span style={{ fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 999, background: "rgba(16,185,129,0.15)", color: "var(--accent)", border: "1px solid rgba(16,185,129,0.3)", marginLeft: "auto" }}>NEW</span>
            )}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className={`sidebar-status${connected ? " sidebar-status--connected" : ""}`}>
          <span className={`status-dot${connected ? " connected" : ""}`} style={{ width: 8, height: 8 }} />
          {!collapsed && (
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                localhost:4566
              </div>
              <div style={{ fontSize: 11, color: "var(--text-faint)" }}>
                {connected ? `Online${version ? ` · v${version}` : ""}` : "Offline"}
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ connected, serviceStatus, version, resourceCounts, totalResources }: {
  connected: boolean;
  serviceStatus: ServiceStatus;
  version: string | null;
  resourceCounts: ResourceCounts;
  totalResources: number;
}) {
  const allServices = COLUMNS.flat().flatMap((s) => s.services);
  const keys = [...new Set(allServices.map((s) => s.healthKey).filter(Boolean) as string[])];
  const healthy = keys.filter((k) => ["available", "running"].includes(serviceStatus[k] ?? "")).length;
  const errors  = keys.filter((k) => serviceStatus[k] === "error").length;

  const [grafanaInput, setGrafanaInput] = useState("http://localhost:3002");
  const [grafanaUrl, setGrafanaUrl]     = useState("http://localhost:3002");
  const [showGrafana, setShowGrafana]   = useState(false);
  const [vectorInput, setVectorInput]   = useState("http://localhost:8686");
  const [vectorUrl, setVectorUrl]       = useState("http://localhost:8686");
  const [vectorHealth, setVectorHealth] = useState<"unknown" | "ok" | "error">("unknown");
  const [search, setSearch]             = useState("");

  useEffect(() => {
    const g = localStorage.getItem("grafanaUrl");
    const v = localStorage.getItem("vectorUrl");
    if (g) { setGrafanaUrl(g); setGrafanaInput(g); }
    if (v) { setVectorUrl(v); setVectorInput(v); }
  }, []);

  useEffect(() => {
    fetch(`/api/vector?base=${encodeURIComponent(vectorUrl)}&path=/health`)
      .then((r) => setVectorHealth(r.ok ? "ok" : "error"))
      .catch(() => setVectorHealth("error"));
  }, [vectorUrl]);

  const q = search.trim().toLowerCase();

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="page-subtitle">All AWS services available in KumoStack</p>
        </div>
        {version && <span className="version-badge">v{version}</span>}
      </div>

      {/* Stat cards */}
      <div className="stat-cards">
        <div className="stat-card">
          <div className="stat-card-icon stat-card-icon--blue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          </div>
          <div>
            <div className="stat-value">{connected ? keys.length : "—"}</div>
            <div className="stat-label">Total Services</div>
          </div>
        </div>
        <div className={`stat-card ${connected && healthy > 0 ? "stat-card--green" : ""}`}>
          <div className="stat-card-icon stat-card-icon--green">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <div>
            <div className="stat-value">{connected ? healthy : "—"}</div>
            <div className="stat-label">Healthy</div>
          </div>
        </div>
        <div className={`stat-card ${connected && errors > 0 ? "stat-card--red" : ""}`}>
          <div className="stat-card-icon stat-card-icon--orange">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div>
            <div className="stat-value">{connected ? totalResources : "—"}</div>
            <div className="stat-label">Total Resources</div>
          </div>
        </div>
        <div className={`stat-card ${connected ? "stat-card--green" : "stat-card--red"}`}>
          <div className={`stat-card-icon ${connected ? "stat-card-icon--green" : "stat-card-icon--red"}`}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          </div>
          <div>
            <div className="stat-value" style={{ fontSize: 22 }}>{connected ? "Online" : "Offline"}</div>
            <div className="stat-label">KumoStack</div>
          </div>
        </div>
      </div>

      {/* Service grid */}
      <div className="section-header">
        <h2 className="section-title">Services</h2>
        <input
          className="search overview-search"
          placeholder="Filter services…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="columns">
        {COLUMNS.map((col, ci) => {
          const visible = col.filter((section) => !q || section.services.some((s) => s.name.toLowerCase().includes(q)));
          if (visible.length === 0) return null;
          return (
            <div key={ci} className="col">
              {visible.map((section) => {
                const visibleSvcs = section.services.filter((s) => !q || s.name.toLowerCase().includes(q));
                return (
                  <div key={section.label} className="col-section">
                    <div className="category-label">{section.label}</div>
                    <div className="service-list">
                      {visibleSvcs.map((s) => {
                        const status = s.healthKey ? serviceStatus[s.healthKey] : undefined;
                        const count  = s.resourceKey ? (resourceCounts[s.resourceKey] ?? null) : null;
                        return (
                          <div key={s.name} className="service">
                            <div className="service-icon-wrap">
                              <div className="service-icon">
                                <Image src={s.icon} alt={s.name} width={32} height={32} unoptimized />
                              </div>
                              {connected && status && (
                                <span className={statusDotClass(status)} title={status} />
                              )}
                            </div>
                            <div className="service-name">{s.name}</div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
                              {connected && count !== null && count > 0 && (
                                <span className="resource-count">{count}</span>
                              )}
                              <span className={`badge ${s.badge}`}>
                                {s.badgeText ?? (s.badge === "free" ? "Free" : "")}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Integrations */}
      <div className="section-header" style={{ marginTop: 40 }}>
        <h2 className="section-title">Integrations</h2>
      </div>

      {/* Grafana */}
      <div className="integration-card">
        <div className="integration-card-header">
          <div className="integration-card-title">
            <svg width="20" height="20" viewBox="0 0 100 100" fill="none">
              <circle cx="50" cy="50" r="46" stroke="#F46800" strokeWidth="6" />
              <path d="M30 50 Q50 20 70 50 Q50 80 30 50Z" fill="#F46800" opacity="0.8" />
            </svg>
            <span>Grafana</span>
            <span className="integration-badge">Monitoring</span>
          </div>
          <div className="integration-actions">
            <input className="integration-input" value={grafanaInput} onChange={(e) => setGrafanaInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (setGrafanaUrl(grafanaInput), localStorage.setItem("grafanaUrl", grafanaInput))} placeholder="http://localhost:3000" />
            <button className="btn btn-sm" onClick={() => { setGrafanaUrl(grafanaInput); localStorage.setItem("grafanaUrl", grafanaInput); }}>Apply</button>
            <button className="btn btn-sm btn-primary" onClick={() => setShowGrafana(!showGrafana)}>{showGrafana ? "Hide" : "Embed Dashboard"}</button>
            <a href={grafanaUrl} target="_blank" rel="noreferrer" className="btn btn-sm">Open ↗</a>
          </div>
        </div>
        {showGrafana ? (
          <iframe src={grafanaUrl} className="grafana-iframe" title="Grafana Dashboard" />
        ) : (
          <p className="integration-desc">Embed any Grafana dashboard to monitor KumoStack resources. Configure your Grafana URL above and click &ldquo;Embed Dashboard&rdquo;, or open it in a new tab.</p>
        )}
      </div>

      {/* Vector.dev */}
      <div className="integration-card">
        <div className="integration-card-header">
          <div className="integration-card-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <polygon points="12,2 22,21 2,21" stroke="#10B981" strokeWidth="2" fill="none" strokeLinejoin="round" />
              <line x1="12" y1="8" x2="12" y2="15" stroke="#10B981" strokeWidth="2" strokeLinecap="round" />
              <circle cx="12" cy="18" r="1.2" fill="#10B981" />
            </svg>
            <span>Vector.dev</span>
            <span className="integration-badge">Log Pipeline</span>
            <span className={`pill ${vectorHealth === "ok" ? "pill--green" : vectorHealth === "error" ? "pill--red" : "pill--dim"}`}>
              {vectorHealth === "ok" ? "Connected" : vectorHealth === "error" ? "Not running" : "Checking…"}
            </span>
          </div>
          <div className="integration-actions">
            <input className="integration-input" value={vectorInput} onChange={(e) => setVectorInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (setVectorUrl(vectorInput), localStorage.setItem("vectorUrl", vectorInput))} placeholder="http://localhost:8686" />
            <button className="btn btn-sm" onClick={() => { setVectorUrl(vectorInput); localStorage.setItem("vectorUrl", vectorInput); }}>Apply</button>
          </div>
        </div>
        <p className="integration-desc">Route KumoStack logs through Vector for filtering, enrichment, and forwarding to any sink. Start Vector with <code className="inline-code">vector --config vector.toml</code> — see the Logs tab for a sample config.</p>
      </div>

      <div className="footer" style={{ marginTop: 40 }}>
        <div>KumoStack · MIT License · <span className="mono">port 4566</span></div>
        <div>
          <a href="https://github.com/kumailr7/ministack" target="_blank" rel="noreferrer">GitHub</a>
          {" · "}
          <a href="https://hub.docker.com/r/ministackorg/ministack" target="_blank" rel="noreferrer">Docker Hub</a>
        </div>
      </div>
    </div>
  );
}

// ─── Status Tab ───────────────────────────────────────────────────────────────

function StatusTab({ connected, serviceStatus }: { connected: boolean; serviceStatus: ServiceStatus }) {
  const [filter, setFilter] = useState<"all" | "running" | "error" | "idle">("all");
  const rows = COLUMNS.flat().flatMap((section) => section.services.map((s) => ({ ...s, category: section.label })));
  const filtered = rows.filter((s) => {
    const st = s.healthKey ? serviceStatus[s.healthKey] : undefined;
    if (filter === "running") return st === "available" || st === "running";
    if (filter === "error")   return st === "error";
    if (filter === "idle")    return !st || (st !== "available" && st !== "running" && st !== "error");
    return true;
  });
  return (
    <div>
      <div className="page-header">
        <div><h1 className="page-title">Service Status</h1><p className="page-subtitle">Health of every KumoStack service</p></div>
        <div className="filter-pills">
          {(["all","running","error","idle"] as const).map((f) => (
            <button key={f} className={`pill-btn ${filter===f?"active":""}`} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase()+f.slice(1)}
            </button>
          ))}
        </div>
      </div>
      {!connected && <DisconnectedNotice />}
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Service</th><th>Category</th><th>Health Key</th><th>Status</th><th>Type</th></tr></thead>
          <tbody>
            {filtered.map((s) => {
              const status = s.healthKey ? serviceStatus[s.healthKey] : undefined;
              return (
                <tr key={s.name+s.category}>
                  <td><div className="cell-with-icon"><Image src={s.icon} alt={s.name} width={20} height={20} unoptimized /><span>{s.name}</span></div></td>
                  <td className="td-dim">{s.category}</td>
                  <td className="td-mono">{s.healthKey ?? "—"}</td>
                  <td><StatusPill status={connected ? status : undefined} /></td>
                  <td><span className={`badge ${s.badge}`}>{s.badgeText ?? (s.badge==="free"?"Free":"")}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Resource Browser Tab ─────────────────────────────────────────────────────

function ResourceBrowserTab({ connected, serviceStatus, query, setQuery, region, setRegion }: {
  connected: boolean; serviceStatus: ServiceStatus;
  query: string; setQuery: (v: string) => void;
  region: string; setRegion: (v: string) => void;
}) {
  const q = query.trim().toLowerCase();
  return (
    <>
      <div className="page-header">
        <div><h1 className="page-title">Resource Browser</h1><p className="page-subtitle">Explore your KumoStack resources</p></div>
        <div className="header-controls">
          <div className="control">
            <label htmlFor="region">Region</label>
            <select id="region" value={region} onChange={(e) => setRegion(e.target.value)}>
              {REGIONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div className="control">
            <label htmlFor="account">Account ID</label>
            <input id="account" className="mono" defaultValue="000000000000" />
          </div>
        </div>
      </div>
      {!connected && <DisconnectedNotice />}
      <div className="search-wrap">
        <input className="search" placeholder="Which service are you looking for?" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="columns">
        {COLUMNS.map((col, ci) => {
          const visible = col.filter((section) => !q || section.services.some((s) => s.name.toLowerCase().includes(q)));
          if (visible.length === 0) return null;
          return (
            <div key={ci} className="col">
              {visible.map((section) => {
                const visibleSvcs = section.services.filter((s) => !q || s.name.toLowerCase().includes(q));
                return (
                  <div key={section.label} className="col-section">
                    <div className="category-label">{section.label}</div>
                    <div className="service-list">
                      {visibleSvcs.map((s) => {
                        const status = s.healthKey ? serviceStatus[s.healthKey] : undefined;
                        return (
                          <div key={s.name} className="service">
                            <div className="service-icon-wrap">
                              <div className="service-icon"><Image src={s.icon} alt={s.name} width={32} height={32} unoptimized /></div>
                              {connected && status && <span className={statusDotClass(status)} title={status} />}
                            </div>
                            <div className="service-name">{s.name}</div>
                            <span className={`badge ${s.badge}`}>{s.badgeText ?? (s.badge==="free"?"Free":"")}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </>
  );
}

// ─── State Tab ────────────────────────────────────────────────────────────────

interface Snapshot { name: string; timestamp: string }
function StateTab({ connected }: { connected: boolean }) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [flash, setFlash]     = useState("");
  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/state").then((r) => r.json()).then((d) => { setSnapshots(Array.isArray(d) ? d : []); setLoading(false); }).catch(() => { setSnapshots([]); setLoading(false); });
  }, []);
  useEffect(() => { if (connected) load(); }, [connected, load]);
  function notify(msg: string) { setFlash(msg); setTimeout(() => setFlash(""), 3000); }
  async function save() {
    const name = prompt("Snapshot name:", `snapshot-${Date.now()}`);
    if (!name) return;
    const r = await fetch("/api/state", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
    notify(r.ok ? "Snapshot saved." : "Failed to save."); if (r.ok) load();
  }
  async function remove(name: string) {
    if (!confirm(`Delete "${name}"?`)) return;
    const r = await fetch(`/api/state?name=${encodeURIComponent(name)}`, { method: "DELETE" });
    notify(r.ok ? "Deleted." : "Failed to delete."); if (r.ok) load();
  }
  async function restore(name: string) {
    const r = await fetch(`/api/state?name=${encodeURIComponent(name)}`, { method: "PATCH" });
    notify(r.ok ? `Restored "${name}".` : "Failed to restore.");
  }
  return (
    <div>
      <div className="page-header">
        <div><h1 className="page-title">State</h1><p className="page-subtitle">Save and restore KumoStack snapshots</p></div>
        <div className="tab-actions">
          <button className="btn btn-primary" onClick={save} disabled={!connected}>Save Snapshot</button>
          <button className="btn" onClick={load} disabled={!connected}>Refresh</button>
        </div>
      </div>
      {!connected && <DisconnectedNotice />}
      {flash && <div className="flash">{flash}</div>}
      {connected && (
        <div className="card-list">
          {loading && <div className="empty-state">Loading snapshots…</div>}
          {!loading && snapshots.length === 0 && <div className="empty-state">No snapshots yet. Click <strong>Save Snapshot</strong> to persist the current KumoStack state.</div>}
          {snapshots.map((s) => (
            <div key={s.name} className="list-item">
              <div><div className="item-title">{s.name}</div><div className="item-sub">{s.timestamp}</div></div>
              <div className="item-actions">
                <button className="btn btn-sm btn-primary" onClick={() => restore(s.name)}>Restore</button>
                <button className="btn btn-sm btn-danger"  onClick={() => remove(s.name)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── App Inspector Tab ────────────────────────────────────────────────────────

interface ApiRequest { id: string; method: string; service: string; path: string; status: number; duration_ms: number; timestamp: string }
function AppInspectorTab({ connected }: { connected: boolean }) {
  const [requests, setRequests] = useState<ApiRequest[]>([]);
  const [loading, setLoading]   = useState(false);
  const [live, setLive]         = useState(false);
  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/requests").then((r) => r.json()).then((d) => { setRequests(Array.isArray(d) ? d : []); setLoading(false); }).catch(() => { setRequests([]); setLoading(false); });
  }, []);
  useEffect(() => { if (connected) load(); }, [connected, load]);
  useEffect(() => { if (!live || !connected) return; const id = setInterval(load, 3000); return () => clearInterval(id); }, [live, connected, load]);
  return (
    <div>
      <div className="page-header">
        <div><h1 className="page-title">App Inspector</h1><p className="page-subtitle">Live AWS API request trace</p></div>
        <div className="tab-actions">
          <button className={`btn btn-sm ${live ? "btn-primary" : ""}`} onClick={() => setLive(!live)}>{live ? "⏸ Pause" : "▶ Live"}</button>
          <button className="btn btn-sm" onClick={load} disabled={!connected}>Refresh</button>
          <button className="btn btn-sm btn-danger" onClick={() => setRequests([])}>Clear</button>
        </div>
      </div>
      {!connected && <DisconnectedNotice />}
      {connected && (
        <div className="table-wrap">
          {loading && requests.length === 0 && <div className="empty-state">Loading…</div>}
          {!loading && requests.length === 0 && <div className="empty-state">No API requests captured yet.</div>}
          {requests.length > 0 && (
            <table className="data-table">
              <thead><tr><th>Method</th><th>Service</th><th>Path</th><th>Status</th><th>Duration</th><th>Time</th></tr></thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id}>
                    <td><span className={`method-badge method-${r.method.toLowerCase()}`}>{r.method}</span></td>
                    <td className="td-dim">{r.service}</td>
                    <td className="td-mono" style={{ maxWidth: 340, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.path}</td>
                    <td><span className={`pill ${r.status < 400 ? "pill--green" : "pill--red"}`}>{r.status}</span></td>
                    <td className="td-dim">{r.duration_ms}ms</td>
                    <td className="td-dim" style={{ whiteSpace: "nowrap" }}>{r.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Logs Tab ─────────────────────────────────────────────────────────────────

const GRAFANA_LOGS_URL    = "http://localhost:3002/d/96615abc-2831-4da6-9f69-97568618695c/kumostack-e28094-log-pipeline-vector-2b-loki";
const GRAFANA_ARCHIVE_URL = "http://localhost:3002/d/a9f75b19-eb51-4753-85e2-9a19c45773b1";
const LOKI_URL            = "http://localhost:3100";
const VECTOR_API_URL      = "http://localhost:8686";
const GARAGE_ADMIN_URL    = "http://localhost:3903";

function LogsTab({ connected }: { connected: boolean }) {
  const [source, setSource]         = useState<"kumostack" | "loki">("kumostack");
  const [logs, setLogs]             = useState<string[]>([]);
  const [live, setLive]             = useState(false);
  const [vectorHealth, setVectorHealth] = useState<"unknown" | "ok" | "error">("unknown");
  const [lokiHealth,  setLokiHealth]  = useState<"unknown" | "ok" | "error">("unknown");
  const [lokiServices, setLokiServices] = useState<string[]>([]);
  const [lokiService,  setLokiService]  = useState("kumostack");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Check Vector + Loki health
  useEffect(() => {
    fetch(`${VECTOR_API_URL}/health`, { signal: AbortSignal.timeout(3000) })
      .then((r) => setVectorHealth(r.ok ? "ok" : "error"))
      .catch(() => setVectorHealth("error"));

    fetch(`${LOKI_URL}/loki/api/v1/label/service/values`, { signal: AbortSignal.timeout(3000) })
      .then((r) => r.json())
      .then((d) => { setLokiHealth("ok"); setLokiServices(d.data ?? []); })
      .catch(() => setLokiHealth("error"));
  }, []);

  const fetchLogs = useCallback(() => {
    if (source === "kumostack") {
      fetch("/api/logs").then((r) => r.text()).then((text) => {
        setLogs(text.split("\n").filter(Boolean).slice(-500));
      }).catch(() => {});
    } else {
      // Pull from Loki
      const now   = Date.now();
      const start = (now - 5 * 60 * 1000) * 1e6; // 5 min ago in nanoseconds
      const query = encodeURIComponent(`{service="${lokiService}"}`);
      fetch(`${LOKI_URL}/loki/api/v1/query_range?query=${query}&start=${start}&end=${now * 1e6}&limit=200&direction=backward`)
        .then((r) => r.json())
        .then((d) => {
          const lines: string[] = [];
          for (const stream of (d.data?.result ?? [])) {
            for (const [ts, msg] of (stream.values ?? [])) {
              try {
                const obj = JSON.parse(msg);
                lines.push(`[${new Date(Number(ts)/1e6).toISOString()}] [${obj.level ?? "info"}] [${obj.service ?? lokiService}] ${obj.message ?? msg}`);
              } catch {
                lines.push(msg);
              }
            }
          }
          setLogs(lines.sort().slice(-500));
        }).catch(() => {});
    }
  }, [source, lokiService]);

  useEffect(() => { fetchLogs(); }, [source, lokiService]);
  useEffect(() => { if (!live) return; const id = setInterval(fetchLogs, 3000); return () => clearInterval(id); }, [live, fetchLogs]);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [logs]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Logs</h1>
          <p className="page-subtitle">Vector.dev pipeline → Loki → Grafana · S3 archival with lifecycle</p>
        </div>
        <div className="tab-actions">
          <a href={GRAFANA_LOGS_URL} target="_blank" rel="noreferrer" className="btn btn-sm btn-primary">
            Open in Grafana ↗
          </a>
        </div>
      </div>

      {/* Pipeline status cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "Vector.dev",    sub: "Log pipeline · port 8686",                   status: vectorHealth,                   href: `${VECTOR_API_URL}/playground` },
          { label: "Grafana Loki",  sub: `${lokiServices.length} services · port 3100`, status: lokiHealth,                     href: `${LOKI_URL}/metrics` },
          { label: "KumoStack S3",  sub: "s3://kumostack-logs · 30d retention",         status: connected ? "ok" : "unknown",   href: "#" },
          { label: "Garage",        sub: "Cold archive · port 3900 · 365d / 2yr",       status: "ok",                           href: `${GARAGE_ADMIN_URL}/health` },
        ].map(({ label, sub, status, href }) => (
          <a key={label} href={href} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
            <div className={`integration-card ${status === "ok" ? "ext-card--running" : ""}`} style={{ marginBottom: 0, cursor: "pointer" }}>
              <div className="integration-card-header" style={{ marginBottom: 4 }}>
                <div className="integration-card-title" style={{ fontSize: 14 }}>{label}</div>
                <span className={`pill ${status === "ok" ? "pill--green" : status === "error" ? "pill--red" : "pill--dim"}`}>
                  {status === "ok" ? "Running" : status === "error" ? "Down" : "Unknown"}
                </span>
              </div>
              <p style={{ fontSize: 12, color: "var(--text-faint)", margin: 0 }}>{sub}</p>
            </div>
          </a>
        ))}
      </div>

      {/* 3-Tier archiving diagram */}
      <div className="integration-card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div className="integration-card-title">3-Tier Log Archiving Pipeline</div>
          <div style={{ display: "flex", gap: 8 }}>
            <a href={GRAFANA_LOGS_URL} target="_blank" rel="noreferrer" className="btn btn-sm">Live Logs ↗</a>
            <a href={GRAFANA_ARCHIVE_URL} target="_blank" rel="noreferrer" className="btn btn-sm btn-primary">Archiving Dashboard ↗</a>
          </div>
        </div>

        {/* Tier table */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
          {[
            { tier: "Tier 1 — Live", storage: "Grafana Loki", retention: "30 days (default)", badge: "#10b981", note: "Real-time search · LogQL · Alerting" },
            { tier: "Tier 2 — Hot Archive", storage: "KumoStack S3", retention: "7d → IA → GLACIER → 30d expire", badge: "#f59e0b", note: "Fast retrieval · recent incidents" },
            { tier: "Tier 3 — Cold Archive", storage: "Garage", retention: "365d (logs) · 730d (RDS)", badge: "#60a5fa", note: "Compliance · audit trail · cost-efficient" },
          ].map(({ tier, storage, retention, badge, note }) => (
            <div key={tier} style={{ background: "var(--bg-elevated)", border: `1px solid ${badge}30`, borderRadius: "var(--radius)", padding: "12px 14px" }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: badge, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{tier}</div>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{storage}</div>
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 6, fontFamily: "var(--font-mono)" }}>{retention}</div>
              <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{note}</div>
            </div>
          ))}
        </div>

        {/* Vector transform chain */}
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em" }}>Vector pipeline</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", fontSize: 11, fontFamily: "var(--font-mono)" }}>
          {[
            { label: "Docker stdout/stderr", color: "#60a5fa" },
            "→",
            { label: "enrich", color: "#a78bfa" },
            "→",
            { label: "parse_level", color: "#a78bfa" },
            "→",
            { label: "aws_enrich", color: "#a78bfa" },
            "→",
            { label: "Loki", color: "#10b981" },
            "·",
            { label: "S3 (30s)", color: "#f59e0b" },
            "·",
            { label: "Garage (300s)", color: "#60a5fa" },
            "·",
            { label: "stderr errors", color: "#ef4444" },
          ].map((item, i) =>
            typeof item === "string" ? (
              <span key={i} style={{ color: "var(--border-strong)" }}>{item}</span>
            ) : (
              <span key={i} style={{ padding: "1px 7px", borderRadius: 3, background: `${item.color}18`, border: `1px solid ${item.color}35`, color: item.color }}>{item.label}</span>
            )
          )}
        </div>

        <div style={{ marginTop: 12, padding: "8px 12px", background: "var(--bg)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)", fontSize: 11, color: "var(--text-dim)", lineHeight: 1.7 }}>
          <strong style={{ color: "var(--text)" }}>Garage</strong> is a lightweight, self-hosted S3-compatible object store (<a href="https://garagehq.deuxfleurs.fr" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>garagehq.deuxfleurs.fr</a>).
          Unlike KumoStack&apos;s ephemeral S3 emulation, Garage persists data durably to disk and is designed for production use.
          Buckets: <code className="inline-code">logs-cold-archive</code> (365d) · <code className="inline-code">logs-rds-archive</code> (730d).
          Vector ships gzip-compressed JSON batches every 300s. Garage&apos;s built-in lifecycle worker runs daily to expire objects past their retention date.
        </div>
      </div>

      {/* Log viewer */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <div className="filter-pills">
          <button className={`pill-btn ${source==="kumostack"?"active":""}`} onClick={() => { setSource("kumostack"); setLogs([]); }}>
            KumoStack (Docker)
          </button>
          <button className={`pill-btn ${source==="loki"?"active":""}`} onClick={() => { setSource("loki"); setLogs([]); }}>
            Loki <span className={`dot-indicator ${lokiHealth==="ok"?"dot--green":"dot--red"}`} />
          </button>
        </div>
        {source === "loki" && lokiServices.length > 0 && (
          <select
            value={lokiService}
            onChange={(e) => { setLokiService(e.target.value); setLogs([]); }}
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: "var(--radius-sm)", padding: "5px 10px", color: "var(--text)", fontSize: 12, fontFamily: "inherit" }}
          >
            {lokiServices.map((s) => <option key={s}>{s}</option>)}
          </select>
        )}
        <button className={`btn btn-sm ${live?"btn-primary":""}`} onClick={() => setLive(!live)}>{live ? "⏸ Pause" : "▶ Live"}</button>
        <button className="btn btn-sm" onClick={fetchLogs}>Refresh</button>
        <button className="btn btn-sm btn-danger" onClick={() => setLogs([])}>Clear</button>
      </div>

      <div className="log-viewer" ref={scrollRef}>
        {logs.length === 0 ? (
          <div className="log-empty">
            {source === "loki" && lokiHealth === "error"
              ? "Loki is not reachable at " + LOKI_URL
              : "No logs yet — click Refresh or enable Live."}
          </div>
        ) : (
          logs.map((line, i) => (
            <div key={i} className={`log-line ${line.includes("error") || line.includes("ERROR") ? "log-line--error" : line.includes("warn") || line.includes("WARN") ? "log-line--warn" : ""}`}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Extensions Tab ───────────────────────────────────────────────────────────

interface DockerConfig { image: string; containerName: string; ports: { host: number; container: number }[]; uiUrl?: string; healthPath?: string; env?: Record<string, string>; }
interface ExtensionDef { name: string; pkg: string; description: string; tags: string[]; repo: string; docker?: DockerConfig; }

const EXTENSION_CATALOG: ExtensionDef[] = [
  { name: "MailHog", pkg: "localstack-extension-mailhog", description: "Captures outgoing SMTP emails and shows them in a web UI. Connect your app's SES or SMTP client to port 1025.", tags: ["Email","Testing"], repo: "https://github.com/localstack/localstack-extensions/tree/main/mailhog", docker: { image: "mailhog/mailhog:latest", containerName: "kumostack-mailhog", ports: [{ host: 1025, container: 1025 }, { host: 8025, container: 8025 }], uiUrl: "http://localhost:8025", healthPath: "/" } },
  { name: "WireMock", pkg: "localstack-wiremock", description: "Stub any HTTP API with flexible request matching and response templating. Perfect for mocking third-party services.", tags: ["Mocking","HTTP"], repo: "https://github.com/localstack/localstack-extensions/tree/main/wiremock", docker: { image: "wiremock/wiremock:latest", containerName: "kumostack-wiremock", ports: [{ host: 8088, container: 8080 }], uiUrl: "http://localhost:8088/__admin/", healthPath: "__admin/health" } },
  { name: "Stripe Mock", pkg: "localstack-extension-stripe", description: "Full Stripe API mock — create charges, customers, subscriptions, and webhooks locally without touching the real Stripe sandbox.", tags: ["Payments","Mock"], repo: "https://github.com/localstack/localstack-extensions/tree/main/stripe", docker: { image: "stripe/stripe-mock:latest", containerName: "kumostack-stripe", ports: [{ host: 12111, container: 12111 }], uiUrl: "http://localhost:12111" } },
  { name: "httpbin", pkg: "localstack-extension-httpbin", description: "HTTP request & response testing service. Inspect headers, query params, redirects, and delays.", tags: ["HTTP","Testing"], repo: "https://github.com/localstack/localstack-extensions/tree/main/httpbin", docker: { image: "kennethreitz/httpbin:latest", containerName: "kumostack-httpbin", ports: [{ host: 8083, container: 80 }], uiUrl: "http://localhost:8083", healthPath: "/get" } },
  { name: "TypeDB", pkg: "localstack-extension-typedb", description: "Polymorphic database for complex domain modelling. Run knowledge-graph queries using TypeQL alongside your AWS services.", tags: ["Database","Graph"], repo: "https://github.com/localstack/localstack-extensions/tree/main/typedb", docker: { image: "vaticle/typedb:latest", containerName: "kumostack-typedb", ports: [{ host: 1729, container: 1729 }] } },
  { name: "ParadeDB", pkg: "localstack-extension-paradedb", description: "PostgreSQL with built-in full-text and vector search. Drop-in Elasticsearch replacement that speaks SQL.", tags: ["Database","Search"], repo: "https://github.com/localstack/localstack-extensions/tree/main/paradedb", docker: { image: "paradedb/paradedb:latest", containerName: "kumostack-paradedb", ports: [{ host: 5435, container: 5432 }], env: { POSTGRESQL_PASSWORD: "kumostack", POSTGRESQL_USERNAME: "kumostack", POSTGRESQL_DATABASE: "kumostack" } } },
  { name: "Miniflare", pkg: "localstack-extension-miniflare", description: "Emulate Cloudflare Workers locally alongside your AWS services. Useful for edge + cloud hybrid architectures.", tags: ["Cloudflare","Edge"], repo: "https://github.com/localstack/localstack-extensions/tree/main/miniflare" },
  { name: "AWS Proxy", pkg: "localstack-extension-aws-proxy", description: "Transparently proxies specific AWS service calls to real AWS while keeping the rest local.", tags: ["Proxy","AWS"], repo: "https://github.com/localstack/localstack-extensions/tree/main/aws-proxy" },
  { name: "Terraform Init", pkg: "localstack-extension-terraform-init", description: "Automatically initialises Terraform providers when LocalStack starts, reducing cold-start friction.", tags: ["IaC","Terraform"], repo: "https://github.com/localstack/localstack-extensions/tree/main/terraform-init" },
  { name: "Diagnosis Viewer", pkg: "localstack-extension-diagnosis-viewer", description: "Diagnostic dashboard for inspecting service state, logs, and configuration issues.", tags: ["Debugging","Observability"], repo: "https://github.com/localstack/localstack-extensions/tree/main/diagnosis-viewer" },
  { name: "Hello World", pkg: "localstack-extension-hello-world", description: "Minimal reference extension showing how to scaffold a custom LocalStack extension.", tags: ["Example","Dev"], repo: "https://github.com/localstack/localstack-extensions/tree/main/hello-world" },
];

const TAG_COLORS: Record<string, string> = {
  Email:"#60a5fa",Testing:"#a78bfa",HTTP:"#34d399",Mocking:"#f472b6",Payments:"#fbbf24",Mock:"#f472b6",Cloudflare:"#fb923c",Edge:"#fb923c",IaC:"#4ade80",Terraform:"#4ade80",Proxy:"#60a5fa",AWS:"#f59e0b",Debugging:"#e879f9",Observability:"#e879f9",Database:"#38bdf8",Graph:"#38bdf8",Search:"#38bdf8",Example:"#9ca3af",Dev:"#9ca3af",
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button className="copy-btn" onClick={() => { navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800); }); }} title="Copy">
      {copied ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>}
    </button>
  );
}

function useExtensionDocker(ext: ExtensionDef) {
  const [status, setStatus] = useState<"unknown"|"running"|"stopped"|"starting"|"stopping">("unknown");
  const [error, setError]   = useState("");
  const check = useCallback(async () => {
    if (!ext.docker) return;
    const r = await fetch(`/api/extensions/docker?name=${ext.docker.containerName}`).catch(() => null);
    if (!r) return;
    const d = await r.json().catch(() => null);
    setStatus(d?.running ? "running" : "stopped");
  }, [ext.docker]);
  useEffect(() => { check(); }, [check]);
  async function launch() {
    if (!ext.docker) return; setStatus("starting"); setError("");
    const r = await fetch("/api/extensions/docker", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ext.docker) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { setError(d.error ?? "Failed to launch"); setStatus("stopped"); } else { setTimeout(check, 1500); }
  }
  async function stop() {
    if (!ext.docker) return; setStatus("stopping"); setError("");
    const r = await fetch(`/api/extensions/docker?name=${ext.docker.containerName}`, { method: "DELETE" });
    if (!r.ok) { const d = await r.json().catch(() => ({})); setError(d.error ?? "Failed to stop"); }
    setTimeout(check, 1000);
  }
  return { status, error, launch, stop };
}

function ExtensionCard({ ext }: { ext: ExtensionDef }) {
  const { status, error, launch, stop } = useExtensionDocker(ext);
  const isRunning = status === "running";
  const isBusy    = status === "starting" || status === "stopping";
  return (
    <div className={`ext-card ${isRunning ? "ext-card--running" : ""}`}>
      <div className="ext-card-header">
        <div className="ext-card-name">{ext.name}</div>
        <div style={{ display:"flex",alignItems:"center",gap:6 }}>
          {ext.docker ? (
            <span className={`pill ${isRunning?"pill--green":"pill--dim"}`}>
              {status==="starting"?"Starting…":status==="stopping"?"Stopping…":isRunning?"Running":"Docker"}
            </span>
          ) : <span className="ext-pro-badge">Pro only</span>}
        </div>
      </div>
      <p className="ext-card-desc">{ext.description}</p>
      <div className="ext-card-tags">
        {ext.tags.map((t) => <span key={t} className="ext-tag" style={{ color: TAG_COLORS[t]??"var(--text-dim)", borderColor:`${TAG_COLORS[t]??"var(--border-strong)"}40` }}>{t}</span>)}
      </div>
      {ext.docker && <div className="ext-ports">{ext.docker.ports.map((p) => <span key={p.host} className="ext-port-chip">:{p.host}</span>)}</div>}
      {error && <div className="ext-error">{error}</div>}
      <div className="ext-card-footer">
        {ext.docker ? (
          <div className="ext-actions">
            {isRunning ? (
              <>{ext.docker.uiUrl && <a href={ext.docker.uiUrl} target="_blank" rel="noreferrer" className="btn btn-sm btn-primary">Open UI ↗</a>}<button className="btn btn-sm btn-danger" onClick={stop} disabled={isBusy}>Stop</button></>
            ) : <button className="btn btn-sm btn-primary" onClick={launch} disabled={isBusy}>{status==="starting"?"Launching…":"Launch"}</button>}
            <div className="ext-image-name"><code className="ext-install-cmd">{ext.docker.image}</code><CopyButton text={`docker run -d --name ${ext.docker.containerName} ${ext.docker.ports.map((p) => `-p ${p.host}:${p.container}`).join(" ")} ${ext.docker.image}`} /></div>
          </div>
        ) : (
          <div className="ext-install-row"><code className="ext-install-cmd">localstack extensions install {ext.pkg}</code><CopyButton text={`localstack extensions install ${ext.pkg}`} /></div>
        )}
        <a href={ext.repo} target="_blank" rel="noreferrer" className="ext-repo-link">source ↗</a>
      </div>
    </div>
  );
}

function ExtensionsTab() {
  const [search, setSearch]     = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [view, setView]         = useState<"all"|"docker"|"pro">("all");
  const allTags = [...new Set(EXTENSION_CATALOG.flatMap((e) => e.tags))].sort();
  const visible = EXTENSION_CATALOG.filter((e) => {
    const q = search.trim().toLowerCase();
    return (!q || e.name.toLowerCase().includes(q) || e.description.toLowerCase().includes(q) || e.tags.some((t) => t.toLowerCase().includes(q)))
        && (!activeTag || e.tags.includes(activeTag))
        && (view==="all" || (view==="docker" && !!e.docker) || (view==="pro" && !e.docker));
  });
  return (
    <div>
      <div className="page-header">
        <div><h1 className="page-title">Extensions</h1><p className="page-subtitle">Companion services for KumoStack</p></div>
        <a href="https://github.com/localstack/localstack-extensions" target="_blank" rel="noreferrer" className="btn btn-sm">GitHub ↗</a>
      </div>
      <div className="ext-legend">
        <div className="ext-legend-item"><span className="pill pill--green" style={{ fontSize:11 }}>Docker</span>Runs as a standalone Docker container — launch directly from this dashboard.</div>
        <div className="ext-legend-item"><span className="ext-pro-badge">Pro only</span>Requires LocalStack Pro. Install with the CLI command shown.</div>
      </div>
      <div className="ext-toolbar">
        <input className="search" style={{ flex:1,marginBottom:0 }} placeholder="Search extensions…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="filter-pills">
          {(["all","docker","pro"] as const).map((v) => <button key={v} className={`pill-btn ${view===v?"active":""}`} onClick={() => setView(v)}>{v==="all"?"All":v==="docker"?"Docker (free)":"Pro only"}</button>)}
        </div>
      </div>
      <div className="filter-pills" style={{ marginBottom:20,flexWrap:"wrap" }}>
        {allTags.map((t) => <button key={t} className={`pill-btn ${activeTag===t?"active":""}`} onClick={() => setActiveTag(activeTag===t?null:t)} style={activeTag===t?{borderColor:TAG_COLORS[t]??"var(--accent)",color:TAG_COLORS[t]??"var(--accent)"}:{}}>{t}</button>)}
      </div>
      <div className="ext-grid">{visible.map((ext) => <ExtensionCard key={ext.pkg} ext={ext} />)}</div>
      {visible.length===0 && <div className="empty-state">No extensions match your search.</div>}
    </div>
  );
}

// ─── Organizations Tab ────────────────────────────────────────────────────────

function OrganizationsTab({ activeAccount, setActiveAccount }: {
  activeAccount: Account;
  setActiveAccount: (a: Account) => void;
}) {
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(MOCK_ACCOUNTS[0]);
  const [selectedOu, setSelectedOu]           = useState<OrgUnit | null>(null);
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [newName, setNewName]   = useState("");
  const [newRegion, setNewRegion] = useState("us-east-1");
  const [newOu, setNewOu]       = useState("r-0001");
  const [accounts, setAccounts] = useState<Account[]>(MOCK_ACCOUNTS);
  const [scps, setScps]         = useState<SCP[]>(MOCK_SCPS);

  const ouChildren = (ouId: string) => accounts.filter((a) => a.ouId === ouId);
  const ouDescendantOus = (ouId: string) => MOCK_OUS.filter((o) => o.parentId === ouId);

  const acctCount = (ouId: string): number => {
    const direct = accounts.filter((a) => a.ouId === ouId).length;
    const children = MOCK_OUS.filter((o) => o.parentId === ouId).reduce((s, o) => s + acctCount(o.id), 0);
    return direct + children;
  };

  const handleCreateAccount = () => {
    if (!newName.trim()) return;
    const newId = String(Math.floor(Math.random() * 9e11) + 1e11);
    const colors = ["#3b82f6","#f59e0b","#8b5cf6","#ec4899","#14b8a6","#f97316"];
    const newAcct: Account = {
      id: newId, name: newName.trim(), email: `${newName.trim()}@kumostack.local`,
      status: "ACTIVE", region: newRegion, ouId: newOu, type: "MEMBER",
      color: colors[Math.floor(Math.random() * colors.length)],
    };
    setAccounts([...accounts, newAcct]);
    setShowCreateAccount(false);
    setNewName("");
    setSelectedAccount(newAcct);
  };

  const toggleScpStatus = (id: string) => {
    setScps(scps.map((s) => s.id === id ? { ...s, status: s.status === "ENABLED" ? "DISABLED" : "ENABLED" } : s));
  };

  const attachedLabel = (attachedTo: string[]) =>
    attachedTo.map((id) => {
      const ou = MOCK_OUS.find((o) => o.id === id);
      const ac = accounts.find((a) => a.id === id);
      return ou?.name ?? ac?.name ?? id;
    }).join(", ");

  const AccountRow = ({ a, indent }: { a: Account; indent: number }) => (
    <div style={{ paddingLeft: indent }}>
      <button
        className={`org-tree-node${selectedAccount?.id === a.id ? " org-tree-node--selected" : ""}${a.id === activeAccount.id ? " org-tree-node--active-acct" : ""}`}
        onClick={() => { setSelectedAccount(a); setSelectedOu(null); }}
      >
        <span className="acct-dot" style={{ background: a.color, width: 8, height: 8, flexShrink: 0 }} />
        <span style={{ fontSize: 13, flex: 1, textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.name}</span>
        {a.type === "MANAGEMENT" && <span className="org-badge org-badge--root">ROOT</span>}
        {a.status === "SUSPENDED" && <span className="org-badge org-badge--suspended">SUSPENDED</span>}
        {a.id === activeAccount.id && (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5" style={{ flexShrink: 0 }}><polyline points="20 6 9 17 4 12"/></svg>
        )}
      </button>
    </div>
  );

  const OuNode = ({ ou, depth }: { ou: OrgUnit; depth: number }) => {
    const subOus      = ouDescendantOus(ou.id);
    const allMembers  = ouChildren(ou.id);
    const mgmt        = allMembers.filter((a) => a.type === "MANAGEMENT");
    const members     = allMembers.filter((a) => a.type === "MEMBER");
    const isRoot      = ou.parentId === null;
    return (
      <div style={{ paddingLeft: depth * 16 }}>
        <button
          className={`org-tree-node org-tree-node--ou${selectedOu?.id === ou.id ? " org-tree-node--selected" : ""}`}
          onClick={() => { setSelectedOu(ou); setSelectedAccount(null); }}
        >
          <span style={{ fontSize: 13, marginRight: 6 }}>{isRoot ? "🏛" : "📁"}</span>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{ou.name}</span>
          <span className="org-badge">{acctCount(ou.id)}</span>
        </button>
        {/* Management accounts first, then child OUs, then member accounts */}
        {mgmt.map((a) => <AccountRow key={a.id} a={a} indent={16} />)}
        {subOus.map((c) => <OuNode key={c.id} ou={c} depth={depth + 1} />)}
        {members.map((a) => <AccountRow key={a.id} a={a} indent={16} />)}
      </div>
    );
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Organizations</h1>
          <p className="page-subtitle">Manage accounts, OUs, and Service Control Policies</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateAccount(true)} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Account
        </button>
      </div>

      {/* Create Account Modal */}
      {showCreateAccount && (
        <div className="org-modal-overlay" onClick={() => setShowCreateAccount(false)}>
          <div className="org-modal" onClick={(e) => e.stopPropagation()}>
            <div className="org-modal-header">
              <span style={{ fontWeight: 700, fontSize: 14 }}>Create Account</span>
              <button onClick={() => setShowCreateAccount(false)} style={{ background: "none", border: "none", color: "var(--text-dim)", cursor: "pointer" }}>✕</button>
            </div>
            <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-dim)", letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>Account Name</label>
                <input className="search" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. payments-team" style={{ width: "100%", marginBottom: 0 }} />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-dim)", letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>Default Region</label>
                <select value={newRegion} onChange={(e) => setNewRegion(e.target.value)} style={{ width: "100%", background: "var(--bg-card)", border: "1px solid var(--border-strong)", padding: "8px 12px", color: "var(--text)", fontSize: 13, borderRadius: "var(--radius-sm)" }}>
                  {REGIONS.map((r) => <option key={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-dim)", letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>Organizational Unit</label>
                <select value={newOu} onChange={(e) => setNewOu(e.target.value)} style={{ width: "100%", background: "var(--bg-card)", border: "1px solid var(--border-strong)", padding: "8px 12px", color: "var(--text)", fontSize: 13, borderRadius: "var(--radius-sm)" }}>
                  {MOCK_OUS.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div style={{ display: "flex", gap: 10, paddingTop: 4 }}>
                <button className="btn-primary" onClick={handleCreateAccount} style={{ flex: 1 }}>Create</button>
                <button className="pill-btn" onClick={() => setShowCreateAccount(false)} style={{ flex: 1 }}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main grid: tree + detail panel */}
      <div className="org-grid">
        {/* Tree */}
        <div className="org-tree-panel">
          <div className="section-header">ORGANIZATION TREE</div>
          <div className="org-tree-scroll">
            {MOCK_OUS.filter((o) => o.parentId === null).map((root) => (
              <OuNode key={root.id} ou={root} depth={0} />
            ))}
          </div>
          <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)" }}>
            <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{accounts.length} accounts · {MOCK_OUS.length} OUs</div>
          </div>
        </div>

        {/* Detail panel */}
        <div className="org-detail-panel">
          {!selectedAccount && !selectedOu && (
            <div className="empty-state" style={{ margin: "auto" }}>Select an account or OU to view details</div>
          )}

          {selectedOu && (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
                <span style={{ fontSize: 24 }}>{selectedOu.parentId === null ? "🏛" : "📁"}</span>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text)" }}>{selectedOu.name}</div>
                  <div style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "var(--font-mono, monospace)" }}>{selectedOu.id}</div>
                </div>
              </div>
              <div className="org-detail-grid">
                <div className="org-detail-cell"><div className="org-detail-label">Accounts</div><div className="org-detail-value">{acctCount(selectedOu.id)}</div></div>
                <div className="org-detail-cell"><div className="org-detail-label">SCPs Attached</div><div className="org-detail-value">{scps.filter((s) => s.attachedTo.includes(selectedOu.id)).length}</div></div>
              </div>
              <div className="section-header" style={{ marginTop: 24, marginBottom: 12 }}>MEMBER ACCOUNTS</div>
              {ouChildren(selectedOu.id).map((a) => (
                <div key={a.id} className="org-acct-row" onClick={() => { setSelectedAccount(a); setSelectedOu(null); }}>
                  <span className="acct-dot" style={{ background: a.color }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{a.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "var(--font-mono, monospace)" }}>{a.id}</div>
                  </div>
                  <span className={`pill ${a.status === "ACTIVE" ? "pill--green" : "pill--red"}`}>{a.status}</span>
                </div>
              ))}
              {ouChildren(selectedOu.id).length === 0 && <div style={{ fontSize: 13, color: "var(--text-faint)", padding: "12px 0" }}>No accounts in this OU</div>}
            </div>
          )}

          {selectedAccount && (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", background: selectedAccount.color + "20", border: `2px solid ${selectedAccount.color}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span className="acct-dot" style={{ background: selectedAccount.color, width: 14, height: 14 }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text)" }}>{selectedAccount.name}</div>
                  <div style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "var(--font-mono, monospace)" }}>ID: {selectedAccount.id}</div>
                </div>
                <span className={`pill ${selectedAccount.status === "ACTIVE" ? "pill--green" : "pill--red"}`}>{selectedAccount.status}</span>
              </div>

              <div className="org-detail-grid">
                <div className="org-detail-cell"><div className="org-detail-label">Region</div><div className="org-detail-value" style={{ fontSize: 13 }}>{selectedAccount.region}</div></div>
                <div className="org-detail-cell"><div className="org-detail-label">Type</div><div className="org-detail-value" style={{ fontSize: 13 }}>{selectedAccount.type}</div></div>
                <div className="org-detail-cell"><div className="org-detail-label">Email</div><div className="org-detail-value" style={{ fontSize: 11, fontFamily: "var(--font-mono, monospace)" }}>{selectedAccount.email}</div></div>
                <div className="org-detail-cell"><div className="org-detail-label">OU</div><div className="org-detail-value" style={{ fontSize: 13 }}>{MOCK_OUS.find((o) => o.id === selectedAccount.ouId)?.name ?? "Root"}</div></div>
              </div>

              {/* STS snippet */}
              <div className="section-header" style={{ marginTop: 24, marginBottom: 10 }}>CROSS-ACCOUNT ACCESS</div>
              <pre style={{ background: "var(--bg-card)", border: "1px solid var(--border)", padding: "12px 16px", fontSize: 11, color: "var(--text-dim)", overflowX: "auto", borderRadius: "var(--radius-sm)", lineHeight: 1.6 }}>{`awslocal sts assume-role \\
  --role-arn arn:aws:iam::${selectedAccount.id}:role/CrossAccountRole \\
  --role-session-name MySession`}</pre>

              <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
                {selectedAccount.id !== activeAccount.id && (
                  <button className="btn-primary" onClick={() => setActiveAccount(selectedAccount)} style={{ flex: 1 }}>
                    Switch to this account
                  </button>
                )}
                {selectedAccount.id === activeAccount.id && (
                  <div style={{ flex: 1, textAlign: "center", fontSize: 12, color: "var(--accent)", fontWeight: 600, padding: "8px 0" }}>✓ Currently active</div>
                )}
                <button
                  className="pill-btn"
                  onClick={() => setAccounts(accounts.map((a) => a.id === selectedAccount.id ? { ...a, status: a.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE" } : a))}
                  style={selectedAccount.status === "ACTIVE" ? { color: "#ef4444", borderColor: "#ef444440" } : { color: "var(--accent)", borderColor: "var(--accent-dim)" }}
                >
                  {selectedAccount.status === "ACTIVE" ? "Suspend" : "Reactivate"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Service Control Policies */}
      <div className="section-header" style={{ marginTop: 40, marginBottom: 16 }}>SERVICE CONTROL POLICIES</div>
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Policy", "Description", "Attached To", "Services", "Effect", "Status"].map((h) => (
                <th key={h} style={{ padding: "10px 16px", fontSize: 11, fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.07em", textAlign: "left" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scps.map((s) => (
              <tr key={s.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "12px 16px", fontSize: 13, fontWeight: 600, color: "var(--text)", fontFamily: "var(--font-mono, monospace)" }}>{s.name}</td>
                <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--text-dim)", maxWidth: 220 }}>{s.description}</td>
                <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--text-dim)" }}>{attachedLabel(s.attachedTo)}</td>
                <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--text-dim)" }}>{s.services.join(", ")}</td>
                <td style={{ padding: "12px 16px" }}>
                  <span className={`pill ${s.effect === "DENY" ? "pill--red" : "pill--green"}`}>{s.effect}</span>
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <button
                    onClick={() => toggleScpStatus(s.id)}
                    className={`pill ${s.status === "ENABLED" ? "pill--green" : "pill--dim"}`}
                    style={{ cursor: "pointer", border: "none", fontWeight: 700, fontSize: 11 }}
                  >
                    {s.status}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Cross-account access log */}
      <div className="section-header" style={{ marginTop: 40, marginBottom: 16 }}>CROSS-ACCOUNT ACCESS LOG</div>
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
        {[
          { time: "just now",   src: "dev-team",   dst: "staging",    role: "DeployRole",       action: "sts:AssumeRole" },
          { time: "2 min ago",  src: "management", dst: "production", role: "ReadOnlyRole",     action: "sts:AssumeRole" },
          { time: "5 min ago",  src: "dev-team",   dst: "management", role: "BillingRole",      action: "sts:AssumeRole" },
          { time: "12 min ago", src: "staging",    dst: "production", role: "CrossAccountRole", action: "sts:AssumeRole" },
        ].map((e, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 16px", borderBottom: i < 3 ? "1px solid var(--border)" : "none", fontSize: 12 }}>
            <span style={{ color: "var(--text-faint)", minWidth: 70 }}>{e.time}</span>
            <span style={{ fontWeight: 600, color: "var(--text)" }}>{e.src}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            <span style={{ fontWeight: 600, color: "var(--text)" }}>{e.dst}</span>
            <span style={{ color: "var(--text-dim)", flex: 1, fontFamily: "var(--font-mono, monospace)" }}>{e.role}</span>
            <span className="pill pill--green" style={{ fontSize: 10 }}>{e.action}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [connected, setConnected]         = useState(false);
  const [activeTab, setActiveTab]         = useState("Overview");
  const [region, setRegion]               = useState("us-east-1");
  const [query, setQuery]                 = useState("");
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({});
  const [version, setVersion]             = useState<string | null>(null);
  const [collapsed, setCollapsed]         = useState(false);
  const [resourceCounts, setResourceCounts] = useState<ResourceCounts>({});
  const [totalResources, setTotalResources] = useState(0);
  const [activeAccount, setActiveAccount] = useState<Account>(MOCK_ACCOUNTS[1]);

  useEffect(() => {
    const poll = () => {
      fetch("/api/health").then((r) => r.json()).then((data) => {
        if (data.services) { setConnected(true); setServiceStatus(data.services); if (data.version) setVersion(data.version); }
        else setConnected(false);
      }).catch(() => setConnected(false));
    };
    poll();
    const id = setInterval(poll, 10_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!connected) return;
    const fetchCounts = () => {
      fetch("/api/resources").then((r) => r.json()).then((d) => {
        if (d.counts) { setResourceCounts(d.counts); setTotalResources(d.total ?? 0); }
      }).catch(() => {});
    };
    fetchCounts();
    const id = setInterval(fetchCounts, 30_000);
    return () => clearInterval(id);
  }, [connected]);

  return (
    <div className="app-shell">
      <Sidebar
        activeTab={activeTab}
        setTab={setActiveTab}
        connected={connected}
        version={version}
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        activeAccount={activeAccount}
        setActiveAccount={setActiveAccount}
      />
      <main className={`app-main${["Stackport","Diagrams"].includes(activeTab) ? " app-main--fullscreen" : ""}`}>
        {activeTab === "Overview"       && <OverviewTab connected={connected} serviceStatus={serviceStatus} version={version} resourceCounts={resourceCounts} totalResources={totalResources} />}
        {activeTab === "Organizations"  && <OrganizationsTab activeAccount={activeAccount} setActiveAccount={setActiveAccount} />}
        {activeTab === "Stackport"      && <StackportTab />}
        {activeTab === "Diagrams"       && <DiagramsTab />}
        {activeTab === "Tutorials"      && <TutorialsTab />}
        {activeTab === "Status"         && <StatusTab connected={connected} serviceStatus={serviceStatus} />}
        {activeTab === "State"          && <StateTab connected={connected} />}
        {activeTab === "App Inspector"  && <AppInspectorTab connected={connected} />}
        {activeTab === "Logs"           && <LogsTab connected={connected} />}
        {activeTab === "Extensions"     && <ExtensionsTab />}
        {activeTab === "Architecture"   && <ArchitectureTab connected={connected} />}
      </main>
    </div>
  );
}
