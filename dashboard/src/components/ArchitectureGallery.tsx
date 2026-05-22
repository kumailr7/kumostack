"use client";

import { useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ServiceNode {
  id:    string;
  label: string;
  color: string;
  col:   number;   // explicit column  (determines X)
  row:   number;   // explicit row     (determines Y)
}

interface FlowEdge { from: string; to: string; label?: string }

// A labelled group boundary (dashed rect) drawn behind nodes in the diagram
interface DiagramGroup {
  label: string;
  color: string;
  cols:  [number, number];  // [colStart, colEnd] inclusive
  rows:  [number, number];  // [rowStart, rowEnd] inclusive
}

interface ArchPattern {
  id:          string;
  title:       string;
  company:     string;
  tag:         string;
  tagColor:    string;
  scale:       string;
  problem:     string;
  description: string;
  services:    ServiceNode[];
  groups?:     DiagramGroup[];  // optional cluster boundaries
  edges:       FlowEdge[];
  whyItWorks:  { service: string; reason: string }[];
  designDecisions: string[];
  simulate:    string;   // multi-line CLI snippet
  learnMore:   string;   // URL to AWS Architecture Center / blog
}

// ── Color palette ──────────────────────────────────────────────────────────────

const C = {
  cf:  "#f59e0b",  // CloudFront
  apigw: "#ec4899", // API Gateway
  lambda: "#8b5cf6",
  sqs:  "#3b82f6",
  sns:  "#10b981",
  dynamo: "#f97316",
  s3:   "#f59e0b",
  kinesis: "#6366f1",
  eb:   "#ec4899",  // EventBridge
  sf:   "#06b6d4",  // Step Functions
  rds:  "#f97316",
  ec2:  "#10b981",
  eks:  "#8b5cf6",
  ecs:  "#06b6d4",
  elb:  "#6366f1",
  route53: "#10b981",
  cache: "#6366f1", // ElastiCache
  cog:  "#ec4899",  // Cognito
  sm:   "#ec4899",  // Secrets Manager
  kms:  "#6366f1",
};

// ── Architecture patterns ─────────────────────────────────────────────────────
// Each pattern uses explicit col/row to produce a unique diagram shape.
// col = X position (0 = leftmost), row = Y position (0 = topmost).

const PATTERNS: ArchPattern[] = [
  // ── Snapchat — verified from AWS re:Invent talk (5B Snaps/day, 10M TPS) ──
  {
    id: "snapchat",
    title: "Snapchat — Real-time Messaging at Scale",
    company: "Snap Inc. on AWS",
    tag: "Real Case Study",
    tagColor: "#f59e0b",
    scale: "300M+ DAU · 5B+ Snaps/day · 10M TPS · 900+ EKS nodes · 400TB DynamoDB",
    problem: "Deliver 5 billion Snaps daily to 300M+ daily active users with real-time friend graph lookups, low-latency media delivery, and cost-effective storage — rebuilt entirely on AWS managed services.",
    description: "Snap rebuilt their messaging infrastructure on AWS to eliminate undifferentiated heavy lifting. At 300M+ DAU and 10M+ TPS, a Kubernetes cluster (900+ nodes, 1000+ pods) hosts four internal microservices behind a single gateway: Media Service (stores/retrieves media via S3 + CloudFront), MCS — Message Content Service (tracks message state in DynamoDB), Friend Graph (caches social relationships in ElastiCache Redis across 900+ cache nodes), and Snap DB (persists snap metadata in DynamoDB — 400TB+, growing at 2B+ rows/month). CloudFront serves media from 400+ edge PoPs, giving recipients their Snaps from the nearest cache rather than reaching back to S3. The rebuild delivered a 24% reduction in median latency for image Snap sends.",
    services: [
      // Clients
      { id: "snap-mobile", label: "iOS / Android",      color: "#9ca3af", col: 0, row: 1 },
      // CDN + origin storage (left of cluster)
      { id: "snap-cf",     label: "CloudFront",          color: "#f59e0b", col: 1, row: 0 },
      { id: "snap-s3",     label: "S3 (media)",          color: "#f59e0b", col: 1, row: 2 },
      // EKS gateway
      { id: "snap-gw",     label: "EKS + GW",            color: "#8b5cf6", col: 2, row: 1 },
      // Four microservices inside the EKS cluster
      { id: "snap-media",  label: "Media Service",       color: "#06b6d4", col: 3, row: 0 },
      { id: "snap-mcs",    label: "MCS",                 color: "#3b82f6", col: 3, row: 1 },
      { id: "snap-fg",     label: "Friend Graph",        color: "#10b981", col: 3, row: 2 },
      { id: "snap-snapdb", label: "Snap DB",             color: "#ec4899", col: 3, row: 3 },
      // Data stores (right of cluster)
      { id: "snap-dynamo", label: "DynamoDB",            color: "#f97316", col: 4, row: 1 },
      { id: "snap-cache",  label: "ElastiCache",         color: "#6366f1", col: 4, row: 2 },
    ],
    groups: [
      // EKS cluster boundary — wraps gateway + all 4 microservices
      { label: "EKS Cluster", color: "#8b5cf6", cols: [2, 3], rows: [0, 3] },
    ],
    edges: [
      // Client → CDN + cluster
      { from: "snap-mobile", to: "snap-cf",     label: "media request" },
      { from: "snap-mobile", to: "snap-gw",     label: "API call" },
      // CDN ↔ origin
      { from: "snap-cf",     to: "snap-s3",     label: "origin fetch" },
      // Gateway → microservices
      { from: "snap-gw",     to: "snap-media",  label: "route" },
      { from: "snap-gw",     to: "snap-mcs",    label: "route" },
      { from: "snap-gw",     to: "snap-fg",     label: "route" },
      { from: "snap-gw",     to: "snap-snapdb", label: "route" },
      // Media service → storage
      { from: "snap-media",  to: "snap-s3",     label: "store" },
      { from: "snap-media",  to: "snap-cf",     label: "serve via CDN" },
      // Microservices → data stores
      { from: "snap-mcs",    to: "snap-dynamo", label: "message state" },
      { from: "snap-fg",     to: "snap-cache",  label: "social graph" },
      { from: "snap-snapdb", to: "snap-dynamo", label: "snap metadata" },
    ],
    whyItWorks: [
      { service: "EKS + Gateway", reason: "900+ nodes and 1000+ pods in a single Kubernetes cluster host all four microservices behind one internal gateway. EKS handles pod autoscaling, service discovery, and rolling deployments — Snap scales individual services independently under burst load (Super Bowl, celebrity posts) without touching the client-facing API." },
      { service: "CloudFront",    reason: "400+ PoPs cache Snap images and videos at the edge. The recipient downloads from the nearest PoP — not from S3. This is the primary driver of the 24% median latency reduction observed after migration." },
      { service: "S3",            reason: "Infinitely durable, infinitely scalable object store for all media. Media Service writes once on send; CloudFront reads from S3 as origin. S3 lifecycle policies tier old Snaps to Glacier automatically." },
      { service: "DynamoDB",      reason: "Both MCS and Snap DB use DynamoDB — 400TB+ of data growing at 2B+ rows/month. Single-digit millisecond reads at 10M TPS, no SQL joins, no schema migrations, no read replicas to manage. On-demand capacity mode absorbs viral Snap spikes without pre-provisioning." },
      { service: "ElastiCache",   reason: "Friend Graph caches the social graph across 900+ ElastiCache nodes. Every Snap send triggers a friend-check — at 10M TPS this must be sub-millisecond. Redis SET commands answer friend queries from cache; DynamoDB is only hit on cache miss." },
    ],
    designDecisions: [
      "Each microservice owns its data store. MCS owns its DynamoDB table; Friend Graph owns its ElastiCache cluster. No shared databases — eliminates cross-service schema coupling and lets each service scale its storage independently.",
      "CloudFront + S3 decouple media delivery from the compute tier. Media Service writes to S3 once on Snap send. Every subsequent view is served by CloudFront from the nearest edge — S3 GET requests drop to near-zero after the first view.",
      "ElastiCache (Redis) is the latency key. Friend Graph does NOT call DynamoDB on every Snap send — it reads from a warm Redis SET. The cache is updated asynchronously when friendships change. Cache-aside pattern with 30-minute TTL.",
      "EKS gateway pattern: a single ingress point routes to all internal services. Clients only know one endpoint. Independent deployments, per-service circuit breakers, and rate limiting happen inside the cluster without SDK changes.",
    ],
    simulate: `# Scale: 300M DAU · 5B+ Snaps/day · 10M TPS · 900+ EKS nodes · 400TB DynamoDB

# 1. EKS cluster (KumoStack simulates the control plane)
aws eks create-cluster --name snap-cluster \\
  --kubernetes-version 1.29 \\
  --resources-vpc-config subnetIds=subnet-0001,securityGroupIds=sg-0001 \\
  --endpoint-url http://localhost:4566

# 2. DynamoDB tables (MCS message state + Snap DB metadata)
#    Production: 400TB+, growing 2B+ rows/month, on-demand billing
aws dynamodb create-table --table-name mcs-messages \\
  --attribute-definitions AttributeName=messageId,AttributeType=S \\
  --key-schema AttributeName=messageId,KeyType=HASH \\
  --billing-mode PAY_PER_REQUEST \\
  --endpoint-url http://localhost:4566

aws dynamodb create-table --table-name snap-metadata \\
  --attribute-definitions AttributeName=snapId,AttributeType=S \\
  --key-schema AttributeName=snapId,KeyType=HASH \\
  --billing-mode PAY_PER_REQUEST \\
  --endpoint-url http://localhost:4566

# 3. S3 bucket for media blobs (CloudFront origin)
aws s3 mb s3://snap-media --endpoint-url http://localhost:4566

# 4. ElastiCache cluster (Friend Graph — 900+ nodes in prod)
aws elasticache create-cache-cluster \\
  --cache-cluster-id snap-friend-graph \\
  --cache-node-type cache.r6g.large \\
  --engine redis --num-cache-nodes 1 \\
  --endpoint-url http://localhost:4566

# 5. Simulate a Snap send: media to S3 + metadata to DynamoDB
aws s3 cp ./snap.jpg s3://snap-media/snaps/snap-001.jpg \\
  --endpoint-url http://localhost:4566

aws dynamodb put-item --table-name snap-metadata \\
  --item '{"snapId":{"S":"snap-001"},"from":{"S":"alice"},"to":{"S":"bob"},"mediaKey":{"S":"snaps/snap-001.jpg"},"ttl":{"N":"1798000000"}}' \\
  --endpoint-url http://localhost:4566`,
    learnMore: "https://aws.amazon.com/video/watch/a8aefa9c875/",
  },
];

// ── Service flow diagram ───────────────────────────────────────────────────────

// ── AWS icon paths (served from /svg/ mount) ──────────────────────────────────

const AWS_ICONS: Record<string, string> = {
  lambda:    "/svg/Compute/Lambda.svg",
  sqs:       "/svg/App-Integration/Simple-Queue-Service.svg",
  sns:       "/svg/App-Integration/Simple-Notification-Service.svg",
  dynamo:    "/svg/Database/DynamoDB.svg",
  s3:        "/svg/Storage/Simple-Storage-Service.svg",
  cf:        "/svg/Networking-Content-Delivery/CloudFront.svg",
  apigw:     "/svg/App-Integration/API-Gateway.svg",
  eb:        "/svg/App-Integration/EventBridge.svg",
  kinesis:   "/svg/Analytics/Kinesis-Data-Streams.svg",
  fh:        "/svg/Analytics/Kinesis-Firehose.svg",
  sf:        "/svg/App-Integration/Step-Functions.svg",
  rds:       "/svg/Database/RDS.svg",
  cache:     "/svg/Database/ElastiCache.svg",
  ec2:       "/svg/Compute/EC2.svg",
  ecs:       "/svg/Containers/Elastic-Container-Service.svg",
  eks:       "/svg/Containers/Elastic-Kubernetes-Service.svg",
  elb:       "/svg/Networking-Content-Delivery/Elastic-Load-Balancing.svg",
  route53:   "/svg/Networking-Content-Delivery/Route-53.svg",
  cog:       "/svg/Security-Identity-Compliance/Cognito.svg",
  sm:        "/svg/Security-Identity-Compliance/Secrets-Manager.svg",
  kms:       "/svg/Security-Identity-Compliance/Key-Management-Service.svg",
  cw:        "/svg/Management-Governance/CloudWatch.svg",
  glue:      "/svg/Analytics/Glue.svg",
  athena:    "/svg/Analytics/Athena.svg",
  batch:     "/svg/Compute/Batch.svg",
};

// ── Flow diagram — explicit col/row grid positioning ──────────────────────────

// Strip pattern-specific prefix (e.g. "vs-cf" → "cf", "rs-apigw" → "apigw")
function _iconKey(id: string): string {
  const stripped = id.replace(/^[a-z]+-/, "");   // remove "vs-", "rs-", "ec-" etc.
  // Known aliases
  const aliases: Record<string, string> = {
    lam: "lambda", lam1: "lambda", lam2: "lambda", lam3: "lambda",
    lamloc: "lambda", lamf: "lambda",
    alb1: "elb", alb2: "elb",
    ecs1: "ecs", ecs2: "ecs",
    rds1: "rds", rds2: "rds",
    s3data: "s3", s3out: "s3", s3up: "s3", s3mdl: "s3", s3mdl2: "s3",
    ddb: "dynamo", stream: "dynamo",
    "lam-a": "lambda", "lam-b": "lambda",
    glue: "glue",
    kin: "kinesis",
  };
  return aliases[stripped] ?? stripped.replace(/\d+$/, "");
}

function FlowDiagram({ services, edges, groups }: {
  services: ServiceNode[];
  edges:    FlowEdge[];
  groups?:  DiagramGroup[];
}) {
  const COL_W = 200, ROW_H = 105, NODE_W = 160, NODE_H = 68, ICON = 32;
  const PAD   = 16;

  const maxCol = Math.max(...services.map(s => s.col));
  const maxRow = Math.max(...services.map(s => s.row));
  const svgW   = (maxCol + 1) * COL_W + PAD * 2;
  const svgH   = (maxRow + 1) * ROW_H + PAD * 2;

  // Explicit grid position for each node
  const pos: Record<string, { x: number; y: number }> = {};
  for (const s of services) {
    pos[s.id] = { x: PAD + s.col * COL_W, y: PAD + s.row * ROW_H };
  }

  // Unique marker id per diagram to avoid cross-diagram collision
  const markerId = `arr-${services.map(s => s.id).join("")}`.slice(0, 40);

  return (
    <svg width={svgW} height={svgH} style={{ display: "block", minWidth: svgW }}>
      <defs>
        <marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L0,8 L8,4 z" fill="#6b7280" />
        </marker>
      </defs>

      {/* Group boundaries — drawn first so everything sits on top */}
      {(groups ?? []).map((g, gi) => {
        const GRP_PAD = 12;
        const x = PAD + g.cols[0] * COL_W - GRP_PAD;
        const y = PAD + g.rows[0] * ROW_H - GRP_PAD;
        const w = (g.cols[1] - g.cols[0] + 1) * COL_W + NODE_W + GRP_PAD * 2;
        const h = (g.rows[1] - g.rows[0] + 1) * ROW_H + NODE_H - (ROW_H - NODE_H) + GRP_PAD * 2;
        return (
          <g key={gi}>
            <rect x={x} y={y} width={w} height={h} rx="14"
              fill={g.color + "08"} stroke={g.color + "50"}
              strokeWidth="1.5" strokeDasharray="8 4" />
            <rect x={x + 10} y={y - 9} width={g.label.length * 7 + 16} height={18} rx="4"
              fill="#0f172a" />
            <text x={x + 18} y={y + 4}
              fontSize="10" fontWeight="700" fill={g.color}>{g.label}</text>
          </g>
        );
      })}

      {/* Edges — drawn behind nodes */}
      {edges.map(e => {
        const a = pos[e.from], b = pos[e.to];
        if (!a || !b || e.from === e.to) return null;
        const ax = a.x + NODE_W, ay = a.y + NODE_H / 2;
        const bx = b.x,         by = b.y + NODE_H / 2;
        // Use a gentle bezier — horizontal control points
        const cp1x = ax + (bx - ax) * 0.5, cp1y = ay;
        const cp2x = ax + (bx - ax) * 0.5, cp2y = by;
        const midX = (ax + bx) / 2;
        const midY = (ay + by) / 2 - 8;
        return (
          <g key={`${e.from}→${e.to}`}>
            <path d={`M${ax},${ay} C${cp1x},${cp1y} ${cp2x},${cp2y} ${bx},${by}`}
              stroke="#4b5563" strokeWidth="1.5" fill="none" strokeDasharray="6 3"
              markerEnd={`url(#${markerId})`} />
            {e.label && (
              <>
                <rect
                  x={midX - e.label.length * 2.9} y={midY - 8}
                  width={e.label.length * 5.8}    height={13} rx="3"
                  fill="#111827" fillOpacity="0.9" />
                <text x={midX} y={midY}
                  fontSize="8" fill="#9ca3af" textAnchor="middle">{e.label}</text>
              </>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {services.map(s => {
        const p = pos[s.id];
        if (!p) return null;
        const iconSrc = AWS_ICONS[_iconKey(s.id)] ?? null;
        const hasIcon = !!iconSrc;
        const iconX   = p.x + 10;
        const iconY   = p.y + (NODE_H - ICON) / 2;
        const textX   = hasIcon ? p.x + 10 + ICON + 8 : p.x + NODE_W / 2;
        const anchor  = hasIcon ? "start" : "middle";
        const textY   = p.y + NODE_H / 2 + 4;
        // Wrap long labels: split at space for two-line render
        const words   = s.label.split(" ");
        const line1   = words.slice(0, 2).join(" ");
        const line2   = words.slice(2).join(" ");
        return (
          <g key={s.id}>
            <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx="10"
              fill={s.color + "18"} stroke={s.color + "70"} strokeWidth="1.5" />
            {hasIcon && (
              <image href={iconSrc} x={iconX} y={iconY} width={ICON} height={ICON} />
            )}
            <text x={textX} y={line2 ? textY - 7 : textY}
              fontSize="10" fontWeight="700" fill={s.color} textAnchor={anchor}>{line1}</text>
            {line2 && (
              <text x={textX} y={textY + 5}
                fontSize="9" fill={s.color + "cc"} textAnchor={anchor}>{line2}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ── Tag badge ──────────────────────────────────────────────────────────────────

function TagBadge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ fontSize: 10, padding: "2px 9px", borderRadius: 12, background: color + "20", color, border: `1px solid ${color}40`, fontWeight: 700, letterSpacing: "0.04em" }}>
      {label}
    </span>
  );
}

// ── Architecture card ──────────────────────────────────────────────────────────

function ArchCard({ pattern, onSelect, selected }: { pattern: ArchPattern; onSelect: () => void; selected: boolean }) {
  return (
    <div onClick={onSelect}
      style={{ background: "var(--bg-card)", border: `1.5px solid ${selected ? pattern.tagColor : "var(--border)"}`, borderRadius: 12, padding: "18px 20px", cursor: "pointer", transition: "border-color 0.2s, box-shadow 0.2s", boxShadow: selected ? `0 0 0 1px ${pattern.tagColor}40` : "none" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)", marginBottom: 3 }}>{pattern.title}</div>
          <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{pattern.company}</div>
        </div>
        <TagBadge label={pattern.tag} color={pattern.tagColor} />
      </div>
      <div style={{ fontSize: 11, color: "#f59e0b", fontFamily: "monospace", marginBottom: 8 }}>{pattern.scale}</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>{pattern.problem}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 10 }}>
        {pattern.services.slice(0, 5).map(s => (
          <span key={s.id} style={{ fontSize: 10, padding: "2px 7px", borderRadius: 4, background: s.color + "18", color: s.color, border: `1px solid ${s.color}30` }}>{s.label}</span>
        ))}
        {pattern.services.length > 5 && <span style={{ fontSize: 10, color: "var(--text-faint)" }}>+{pattern.services.length - 5}</span>}
      </div>
    </div>
  );
}

// ── Detail panel ───────────────────────────────────────────────────────────────

function DetailPanel({ pattern }: { pattern: ArchPattern }) {
  const [tab, setTab] = useState<"overview" | "decisions" | "simulate">("overview");

  return (
    <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)", background: `linear-gradient(135deg, ${pattern.tagColor}0a, transparent)` }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text)", margin: 0 }}>{pattern.title}</h3>
            <div style={{ fontSize: 12, color: "var(--text-faint)", marginTop: 3 }}>{pattern.company}</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <TagBadge label={pattern.tag} color={pattern.tagColor} />
            <a href={pattern.learnMore} target="_blank" rel="noreferrer"
              style={{ fontSize: 11, padding: "4px 12px", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-muted)", textDecoration: "none" }}>
              AWS Docs ↗
            </a>
            <a href="https://aws.amazon.com/architecture/" target="_blank" rel="noreferrer"
              style={{ fontSize: 11, padding: "4px 12px", background: pattern.tagColor + "20", border: `1px solid ${pattern.tagColor}40`, borderRadius: 6, color: pattern.tagColor, textDecoration: "none", fontWeight: 600 }}>
              Architecture Center ↗
            </a>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "#f59e0b", fontFamily: "monospace", marginBottom: 6 }}>Scale: {pattern.scale}</div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.6 }}>{pattern.description}</div>
      </div>

      {/* Sub-tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
        {(["overview", "decisions", "simulate"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: "10px 20px", fontSize: 12, fontWeight: tab === t ? 700 : 400, border: "none", borderBottom: tab === t ? `2px solid ${pattern.tagColor}` : "2px solid transparent", background: "transparent", cursor: "pointer", color: tab === t ? pattern.tagColor : "var(--text-muted)", marginBottom: -1, transition: "color 0.15s" }}>
            {t === "overview" ? "Architecture" : t === "decisions" ? "Design Decisions" : "Simulate in KumoStack"}
          </button>
        ))}
      </div>

      <div style={{ padding: "20px 24px" }}>

        {tab === "overview" && (
          <div>
            {/* SVG flow diagram */}
            <div style={{ background: "var(--bg-elevated)", borderRadius: 10, padding: "16px", marginBottom: 20, overflowX: "auto" }}>
              <FlowDiagram services={pattern.services} edges={pattern.edges} groups={pattern.groups} />
            </div>

            {/* Why it works */}
            <div className="section-header" style={{ marginBottom: 12 }}>WHY EACH SERVICE WAS CHOSEN</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {pattern.whyItWorks.map(w => (
                <div key={w.service} style={{ display: "flex", gap: 12, padding: "10px 14px", background: "var(--bg-elevated)", borderRadius: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)", width: 120, flexShrink: 0 }}>{w.service}</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>{w.reason}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "decisions" && (
          <div>
            <div className="section-header" style={{ marginBottom: 12 }}>KEY ARCHITECTURAL DECISIONS</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {pattern.designDecisions.map((d, i) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: "12px 16px", background: "var(--bg-elevated)", borderRadius: 8, borderLeft: `3px solid ${pattern.tagColor}` }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: pattern.tagColor, flexShrink: 0 }}>{i + 1}</div>
                  <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.6 }}>{d}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "simulate" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div className="section-header" style={{ margin: 0 }}>SIMULATE THIS ARCHITECTURE IN KUMOSTACK</div>
              <span style={{ fontSize: 11, color: "var(--text-faint)" }}>Run against http://localhost:4566</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12, padding: "8px 12px", background: "#3b82f610", borderRadius: 6, border: "1px solid #3b82f630", lineHeight: 1.5 }}>
              These commands create the core infrastructure of this pattern locally. KumoStack emulates all the services — no AWS account or cost required.
            </div>
            <pre style={{ fontSize: 12, background: "#0d1117", borderRadius: 8, padding: "16px 18px", overflowX: "auto", lineHeight: 1.7, color: "#e2e8f0", margin: 0, border: "1px solid #1e2530" }}>
              <code>{pattern.simulate}</code>
            </pre>
            <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
              <button onClick={() => navigator.clipboard.writeText(pattern.simulate)}
                style={{ fontSize: 11, padding: "5px 14px", borderRadius: 6, background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)", cursor: "pointer" }}>
                Copy
              </button>
              <a href={pattern.learnMore} target="_blank" rel="noreferrer"
                style={{ fontSize: 11, padding: "5px 14px", borderRadius: 6, background: pattern.tagColor + "20", border: `1px solid ${pattern.tagColor}40`, color: pattern.tagColor, textDecoration: "none", fontWeight: 600 }}>
                Full AWS Guide ↗
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

const TAGS = ["All", ...Array.from(new Set(PATTERNS.map(p => p.tag)))];

export default function ArchitectureGallery() {
  const [selected, setSelected] = useState<ArchPattern>(PATTERNS[0]);
  const [filter,   setFilter]   = useState("All");

  const filtered = filter === "All" ? PATTERNS : PATTERNS.filter(p => p.tag === filter);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>

      {/* AWS Architecture Center banner */}
      <div style={{ padding: "10px 20px", background: "linear-gradient(90deg,#f59e0b18,#f97316 12 0)", borderBottom: "1px solid #f59e0b30", display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><rect x="2" y="3" width="6" height="4" rx="1"/><rect x="16" y="3" width="6" height="4" rx="1"/><rect x="9" y="17" width="6" height="4" rx="1"/><path d="M5 7v4h14V7M12 11v6"/></svg>
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b" }}>AWS Architecture Center</span>
          <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: 10 }}>
            Official AWS reference architectures, whitepapers, and solution guides
          </span>
        </div>
        <a href="https://aws.amazon.com/architecture/" target="_blank" rel="noreferrer"
          style={{ padding: "6px 18px", fontSize: 13, fontWeight: 700, background: "#f59e0b", color: "#000", borderRadius: 7, textDecoration: "none", whiteSpace: "nowrap", letterSpacing: "0.01em" }}>
          Open AWS Architecture Center ↗
        </a>
      </div>

      {/* Toolbar */}
      <div style={{ padding: "10px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12, background: "var(--bg-card)", flexShrink: 0, flexWrap: "wrap" }}>
        <div>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0" }}>Architecture Gallery</span>
          <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: 10 }}>
            Large-scale patterns — how real systems are built at scale
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, marginLeft: "auto", alignItems: "center", flexWrap: "wrap" }}>
          {TAGS.map(t => (
            <button key={t} onClick={() => setFilter(t)}
              style={{ padding: "3px 12px", fontSize: 11, borderRadius: 12, border: "1px solid", cursor: "pointer", borderColor: filter === t ? "#3b82f6" : "var(--border)", background: filter === t ? "#3b82f620" : "transparent", color: filter === t ? "#60a5fa" : "var(--text-muted)", fontWeight: filter === t ? 700 : 400 }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Body: card grid + detail panel */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "320px 1fr", overflow: "hidden" }}>

        {/* Left: card list */}
        <div style={{ overflowY: "auto", borderRight: "1px solid var(--border)", padding: "16px 12px", display: "flex", flexDirection: "column", gap: 10, background: "var(--bg-base)" }}>
          {filtered.map(p => (
            <ArchCard key={p.id} pattern={p} onSelect={() => setSelected(p)} selected={selected.id === p.id} />
          ))}
        </div>

        {/* Right: detail view */}
        <div style={{ overflowY: "auto", padding: "20px", background: "var(--bg-base)" }}>
          <DetailPanel pattern={selected} />
        </div>
      </div>
    </div>
  );
}
