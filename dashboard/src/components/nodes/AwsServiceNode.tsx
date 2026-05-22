"use client";
import { Handle, Position } from "@xyflow/react";

interface NodeData {
  label: string;
  service: string;
  status: string;
  meta: Record<string, string>;
}

const CDN = "/svg";

const SERVICE_META: Record<string, { border: string; category: string; icon: string }> = {
  cloudfront:     { border: "#8C4FFF", category: "CDN",        icon: `${CDN}/Networking-Content-Delivery/CloudFront.svg` },
  s3:             { border: "#3F8624", category: "Storage",     icon: `${CDN}/Storage/Simple-Storage-Service.svg` },
  ec2:            { border: "#F58536", category: "Compute",     icon: `${CDN}/Compute/EC2.svg` },
  alb:            { border: "#8C4FFF", category: "Networking",  icon: `${CDN}/Networking-Content-Delivery/Elastic-Load-Balancing.svg` },
  rds:            { border: "#527FFF", category: "Database",    icon: `${CDN}/Database/RDS.svg` },
  lambda:         { border: "#F58536", category: "Lambda",      icon: `${CDN}/Compute/Lambda.svg` },
  dynamodb:       { border: "#527FFF", category: "DynamoDB",    icon: `${CDN}/Database/DynamoDB.svg` },
  sqs:            { border: "#F58536", category: "SQS",         icon: `${CDN}/App-Integration/Simple-Queue-Service.svg` },
  sns:            { border: "#F58536", category: "SNS",         icon: `${CDN}/App-Integration/Simple-Notification-Service.svg` },
  wafv2:          { border: "#DD344C", category: "WAF",         icon: `${CDN}/Security-Identity-Compliance/WAF.svg` },
  ecr:            { border: "#F58536", category: "ECR",         icon: `${CDN}/Containers/Elastic-Container-Registry.svg` },
  secretsmanager: { border: "#DD344C", category: "Secrets Mgr", icon: `${CDN}/Security-Identity-Compliance/Secrets-Manager.svg` },
  eks:            { border: "#8C4FFF", category: "EKS",         icon: `${CDN}/Containers/Elastic-Kubernetes-Service.svg` },
  ecs:            { border: "#8C4FFF", category: "ECS",         icon: `${CDN}/Containers/Elastic-Container-Service.svg` },
  elasticache:    { border: "#527FFF", category: "ElastiCache", icon: `${CDN}/Database/ElastiCache.svg` },
  opensearch:     { border: "#527FFF", category: "Search",      icon: `${CDN}/Analytics/OpenSearch-Service.svg` },
  apigateway:     { border: "#8C4FFF", category: "API",         icon: `${CDN}/App-Integration/API-Gateway.svg` },
  cloudformation: { border: "#DD344C", category: "IaC",         icon: `${CDN}/Management-Governance/CloudFormation.svg` },
  kinesis:        { border: "#8C4FFF", category: "Streaming",   icon: `${CDN}/Analytics/Kinesis.svg` },
  stepfunctions:  { border: "#F58536", category: "Workflow",    icon: `${CDN}/App-Integration/Step-Functions.svg` },
  internet:       { border: "#3B82F6", category: "Internet",    icon: `${CDN}/Networking-Content-Delivery/CloudFront.svg` },
};

const STATUS_COLOR: Record<string, string> = {
  running:    "#22c55e",
  available:  "#22c55e",
  active:     "#22c55e",
  Deployed:   "#22c55e",
  stopped:    "#ef4444",
  terminated: "#6b7280",
  pending:    "#f59e0b",
  unknown:    "#6b7280",
};

export default function AwsServiceNode({ data }: { data: NodeData }) {
  const cfg = SERVICE_META[data.service] ?? {
    border: "#475569",
    category: data.service,
    icon: `${CDN}/Compute/EC2.svg`,
  };
  const statusColor = STATUS_COLOR[data.status] ?? "#6b7280";

  // Internet node — globe style
  if (data.service === "internet") {
    return (
      <div style={{ width: 120, position: "relative" }}>
        <Handle type="source" position={Position.Right} style={{ background: "#3B82F6", width: 8, height: 8 }} />
        <div style={{
          width: "100%",
          borderRadius: 12,
          background: "#131720",
          border: "1.5px solid #3B82F640",
          boxShadow: "0 0 0 1px #3B82F620, 0 6px 24px rgba(0,0,0,0.5)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}>
          <div style={{ width: "100%", height: 3, background: "#3B82F6", flexShrink: 0 }} />
          <div style={{ padding: "14px 12px 8px", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
            <svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="#60a5fa" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <path d="M2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20" />
            </svg>
            <span style={{ fontSize: 9, fontWeight: 700, color: "#3B82F6", textTransform: "uppercase", letterSpacing: "0.12em" }}>
              Internet
            </span>
          </div>
          <div style={{ width: "80%", height: 1, background: "#3B82F625", marginBottom: 8 }} />
          <div style={{ padding: "0 10px 10px", textAlign: "center" }}>
            <p style={{ fontSize: 12, fontWeight: 800, color: "#f1f5f9", margin: 0 }}>{data.label}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: 150, position: "relative" }}>
      <Handle type="target" position={Position.Left} style={{ background: cfg.border, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: cfg.border, width: 8, height: 8 }} />
      <Handle type="target" position={Position.Top} style={{ background: cfg.border, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: cfg.border, width: 8, height: 8 }} />

      <div style={{
        width: "100%",
        borderRadius: 12,
        background: "#131720",
        border: `1.5px solid ${cfg.border}40`,
        boxShadow: `0 0 0 1px ${cfg.border}20, 0 6px 24px rgba(0,0,0,0.5)`,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}>
        {/* Top accent line in service colour */}
        <div style={{ width: "100%", height: 3, background: cfg.border, flexShrink: 0 }} />

        {/* Icon + category */}
        <div style={{ padding: "14px 12px 8px", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={cfg.icon} alt={data.service} width={44} height={44} style={{ display: "block" }} />
          <span style={{
            fontSize: 9,
            fontWeight: 700,
            color: cfg.border,
            textTransform: "uppercase",
            letterSpacing: "0.12em",
          }}>
            {cfg.category}
          </span>
        </div>

        {/* Divider */}
        <div style={{ width: "80%", height: 1, background: `${cfg.border}25`, marginBottom: 8 }} />

        {/* Resource name */}
        <div style={{ padding: "0 10px 4px", textAlign: "center", width: "100%" }}>
          <p style={{
            fontSize: 12,
            fontWeight: 800,
            color: "#f1f5f9",
            lineHeight: 1.35,
            wordBreak: "break-word",
            margin: 0,
            letterSpacing: "-0.01em",
          }}>
            {data.label}
          </p>
        </div>

        {/* Status + region footer */}
        <div style={{
          width: "100%",
          background: "#0c0f15",
          borderTop: "1px solid rgba(255,255,255,0.04)",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 5, padding: "5px 8px 3px" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, boxShadow: `0 0 6px ${statusColor}`, display: "inline-block", flexShrink: 0 }} />
            <span style={{ fontSize: 10, color: statusColor, textTransform: "capitalize", fontWeight: 600 }}>
              {data.status}
            </span>
          </div>
          {data.meta?.region && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, padding: "0 8px 5px" }}>
              <span style={{ fontSize: 8, color: "#334155" }}>📍</span>
              <span style={{ fontSize: 9, color: "#334155", fontFamily: "monospace", letterSpacing: "0.03em" }}>
                {data.meta.region}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
