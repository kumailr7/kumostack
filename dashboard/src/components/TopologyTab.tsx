"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type NodeProps,
  type Connection,
  BackgroundVariant,
  MarkerType,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

// ── Service metadata ──────────────────────────────────────────────────────────

const SVC_META: Record<string, { color: string; bg: string; label: string; icon: string }> = {
  lambda:        { color: "#8b5cf6", bg: "#8b5cf615", label: "Lambda",        icon: "λ" },
  sqs:           { color: "#3b82f6", bg: "#3b82f615", label: "SQS",           icon: "Q" },
  sns:           { color: "#10b981", bg: "#10b98115", label: "SNS",           icon: "S" },
  dynamodb:      { color: "#f97316", bg: "#f9731615", label: "DynamoDB",      icon: "D" },
  s3:            { color: "#f59e0b", bg: "#f59e0b15", label: "S3",            icon: "S3" },
  eventbridge:   { color: "#ec4899", bg: "#ec489915", label: "EventBridge",   icon: "E" },
  stepfunctions: { color: "#06b6d4", bg: "#06b6d415", label: "Step Fns",     icon: "SF" },
  kinesis:       { color: "#6366f1", bg: "#6366f115", label: "Kinesis",       icon: "K" },
  http:          { color: "#6b7280", bg: "#6b728015", label: "HTTP",          icon: "H" },
};

// ── Tiered layout ─────────────────────────────────────────────────────────────

const TIER: Record<string, number> = {
  eventbridge:   0,
  s3:            1,
  stepfunctions: 1,
  kinesis:       2,
  sns:           2,
  sqs:           3,
  lambda:        4,
  dynamodb:      5,
  http:          5,
};

const NODE_W  = 160;
const NODE_H  = 64;
const TIER_GAP = 220;
const ROW_GAP  = 90;

function buildLayout(
  rawNodes: { id: string; label: string; service: string; arn: string }[],
  rawEdges: { id: string; source: string; target: string; label: string }[]
): { nodes: Node[]; edges: Edge[] } {
  const byTier: Record<number, typeof rawNodes> = {};
  for (const n of rawNodes) {
    const t = TIER[n.service] ?? 3;
    (byTier[t] ??= []).push(n);
  }

  const nodes: Node[] = rawNodes.map(n => {
    const tier     = TIER[n.service] ?? 3;
    const siblings = byTier[tier]!;
    const idx      = siblings.indexOf(n);
    const totalH   = siblings.length * ROW_GAP;
    return {
      id:       n.id,
      type:     "serviceNode",
      position: {
        x: tier * TIER_GAP,
        y: idx * ROW_GAP - totalH / 2 + 400,
      },
      data: { label: n.label, service: n.service, arn: n.arn },
    };
  });

  const edges: Edge[] = rawEdges.map(e => ({
    id:             e.id,
    source:         e.source,
    target:         e.target,
    label:          e.label || undefined,
    labelStyle:     { fontSize: 10, fill: "var(--text-muted, #888)" },
    labelBgStyle:   { fill: "transparent" },
    style:          { stroke: "#4b5563", strokeWidth: 1.5 },
    markerEnd:      { type: MarkerType.ArrowClosed, color: "#4b5563", width: 14, height: 14 },
    animated:       true,
  }));

  return { nodes, edges };
}

// ── Custom node ───────────────────────────────────────────────────────────────

function ServiceNode({ data, selected }: NodeProps) {
  const d    = data as { label: string; service: string; arn: string };
  const meta = SVC_META[d.service] ?? SVC_META.http;
  return (
    <div style={{
      width: NODE_W, minHeight: NODE_H,
      background:   selected ? meta.color + "30" : meta.bg,
      border:       `1.5px solid ${selected ? meta.color : meta.color + "60"}`,
      borderRadius: 10,
      padding:      "8px 12px",
      display:      "flex",
      alignItems:   "center",
      gap:          10,
      boxShadow:    selected ? `0 0 0 2px ${meta.color}` : "none",
      transition:   "box-shadow 0.15s",
      cursor:       "pointer",
    }}>
      <Handle type="target" position={Position.Left}  style={{ opacity: 0 }} />
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: meta.color + "30",
        border: `1px solid ${meta.color}50`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 800, color: meta.color, flexShrink: 0,
      }}>
        {meta.icon}
      </div>
      <div style={{ overflow: "hidden" }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: meta.color, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>
          {meta.label}
        </div>
        <div style={{ fontSize: 11, fontWeight: 600, color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 100 }} title={d.label}>
          {d.label}
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const NODE_TYPES = { serviceNode: ServiceNode };

// ── Side panel ────────────────────────────────────────────────────────────────

function SidePanel({ node, onClose }: { node: Node | null; onClose: () => void }) {
  if (!node) return null;
  const d    = node.data as { label: string; service: string; arn: string };
  const meta = SVC_META[d.service] ?? SVC_META.http;

  const ctUrl = `http://localhost:3003/CloudTrail`;   // open CloudTrail tab in KumoStack dash
  const tempoUrl = `http://localhost:3002/explore?orgId=1&left=${encodeURIComponent(JSON.stringify({
    datasource: "kumostack-tempo",
    queries: [{ refId: "A", queryType: "traceql", query: `{resource.aws.service="${d.service}"}` }],
    range: { from: "now-1h", to: "now" },
  }))}`;

  return (
    <div style={{
      position: "absolute", top: 0, right: 0, bottom: 0,
      width: 280, background: "var(--bg-card, #1e2530)",
      borderLeft: "1px solid var(--border, #2d3748)",
      zIndex: 10, display: "flex", flexDirection: "column",
      boxShadow: "-4px 0 16px #00000040",
    }}>
      <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--border, #2d3748)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, color: meta.color, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{meta.label}</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#e2e8f0", wordBreak: "break-all" }}>{d.label}</div>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--text-muted, #888)", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: 0 }}>×</button>
      </div>

      <div style={{ padding: "14px 18px", flex: 1, overflowY: "auto" }}>
        {d.arn && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text-dim, #6b7280)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>ARN</div>
            <code style={{ fontSize: 10, color: "var(--text-muted, #9ca3af)", wordBreak: "break-all", lineHeight: 1.5, display: "block" }}>{d.arn}</code>
          </div>
        )}

        <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text-dim, #6b7280)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>Quick Links</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <a href={ctUrl} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: meta.color, textDecoration: "none", padding: "6px 10px", background: meta.bg, borderRadius: 6, border: `1px solid ${meta.color}30` }}>
            CloudTrail events ↗
          </a>
          <a href={tempoUrl} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: "#60a5fa", textDecoration: "none", padding: "6px 10px", background: "#3b82f610", borderRadius: 6, border: "1px solid #3b82f630" }}>
            Traces in Tempo ↗
          </a>
        </div>

        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text-dim, #6b7280)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>AWS CLI</div>
          <pre style={{ fontSize: 10, background: "var(--bg-elevated, #111827)", borderRadius: 6, padding: "10px 12px", color: "var(--text-muted, #9ca3af)", overflowX: "auto", margin: 0, lineHeight: 1.6, wordBreak: "break-all", whiteSpace: "pre-wrap" }}>
            {d.service === "lambda"   && `aws lambda get-function \\\n  --function-name ${d.label} \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "sqs"      && `aws sqs get-queue-attributes \\\n  --queue-url http://localhost:4566/000000000000/${d.label} \\\n  --attribute-names All \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "sns"      && `aws sns get-topic-attributes \\\n  --topic-arn arn:aws:sns:us-east-1:000000000000:${d.label} \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "dynamodb" && `aws dynamodb describe-table \\\n  --table-name ${d.label} \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "s3"       && `aws s3 ls s3://${d.label}/ \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "eventbridge" && `aws events list-targets-by-rule \\\n  --rule ${d.label} \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "stepfunctions" && `aws stepfunctions describe-state-machine \\\n  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:${d.label} \\\n  --endpoint-url http://localhost:4566`}
            {d.service === "kinesis"  && `aws kinesis describe-stream \\\n  --stream-name ${d.label} \\\n  --endpoint-url http://localhost:4566`}
          </pre>
        </div>
      </div>
    </div>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

function Legend() {
  return (
    <div style={{ position: "absolute", bottom: 16, left: 16, zIndex: 10, background: "var(--bg-card, #1e2530)", border: "1px solid var(--border, #2d3748)", borderRadius: 8, padding: "10px 14px", display: "flex", flexWrap: "wrap", gap: "8px 16px", maxWidth: 400 }}>
      {Object.entries(SVC_META).filter(([k]) => k !== "http").map(([key, meta]) => (
        <div key={key} style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 10, height: 10, borderRadius: 3, background: meta.color }} />
          <span style={{ fontSize: 10, color: "var(--text-muted, #9ca3af)" }}>{meta.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface RawNode { id: string; label: string; service: string; arn: string }
interface RawEdge { id: string; source: string; target: string; label: string }

export default function TopologyTab() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading,  setLoading]    = useState(true);
  const [selected, setSelected]   = useState<Node | null>(null);
  const [filter,   setFilter]     = useState<string>("all");
  const [rawData,  setRawData]    = useState<{ nodes: RawNode[]; edges: RawEdge[] }>({ nodes: [], edges: [] });

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/topology", { cache: "no-store" });
      const d = await r.json();
      setRawData(d);
      const { nodes: n, edges: e } = buildLayout(d.nodes ?? [], d.edges ?? []);
      setNodes(n);
      setEdges(e);
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => { load(); }, [load]);

  // Re-apply layout when filter changes
  useEffect(() => {
    const filteredNodes = filter === "all"
      ? rawData.nodes
      : rawData.nodes.filter(n => n.service === filter);
    const filteredIds = new Set(filteredNodes.map(n => n.id));
    const filteredEdges = rawData.edges.filter(e => filteredIds.has(e.source) && filteredIds.has(e.target));
    const { nodes: n, edges: e } = buildLayout(filteredNodes, filteredEdges);
    setNodes(n);
    setEdges(e);
  }, [filter, rawData, setNodes, setEdges]);

  const onConnect = useCallback((c: Connection) => setEdges(eds => addEdge(c, eds)), [setEdges]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelected(prev => prev?.id === node.id ? null : node);
  }, []);

  const services = ["all", ...Array.from(new Set(rawData.nodes.map(n => n.service))).sort()];

  const isEmpty = !loading && rawData.nodes.length === 0;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>

      {/* Toolbar */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border, #2d3748)", display: "flex", alignItems: "center", gap: 12, background: "var(--bg-card, #1e2530)", flexShrink: 0 }}>
        <div>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#e2e8f0" }}>Resource Topology</span>
          <span style={{ fontSize: 12, color: "var(--text-muted, #9ca3af)", marginLeft: 10 }}>
            {rawData.nodes.length} resources · {rawData.edges.length} connections
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, marginLeft: "auto", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--text-muted, #9ca3af)" }}>Filter:</span>
          {services.map(svc => {
            const meta = SVC_META[svc];
            return (
              <button key={svc} onClick={() => setFilter(svc)}
                style={{
                  padding: "3px 10px", fontSize: 11, borderRadius: 5, border: "1px solid",
                  cursor: "pointer",
                  borderColor: filter === svc ? (meta?.color ?? "#3b82f6") : "var(--border, #2d3748)",
                  background:  filter === svc ? (meta?.color ?? "#3b82f6") + "20" : "transparent",
                  color:       filter === svc ? (meta?.color ?? "#60a5fa") : "var(--text-muted, #9ca3af)",
                  fontWeight:  filter === svc ? 700 : 400,
                }}>
                {svc === "all" ? "All" : (SVC_META[svc]?.label ?? svc)}
              </button>
            );
          })}
          <button onClick={load} style={{ marginLeft: 8, padding: "3px 12px", fontSize: 11, borderRadius: 5, border: "1px solid var(--border, #2d3748)", background: "transparent", color: "var(--text-muted, #9ca3af)", cursor: "pointer" }}>
            Refresh
          </button>
        </div>
      </div>

      {/* Graph area */}
      <div style={{ flex: 1, position: "relative" }}>
        {loading && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted, #9ca3af)", fontSize: 13 }}>
            Loading topology…
          </div>
        )}

        {isEmpty && (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "var(--text-muted, #9ca3af)", textAlign: "center", padding: 40 }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>🗺️</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "#e2e8f0", marginBottom: 8 }}>No resources yet</div>
            <div style={{ fontSize: 13, maxWidth: 480, lineHeight: 1.6 }}>
              Create some AWS resources — Lambda functions, SQS queues, SNS topics, DynamoDB tables, EventBridge rules — and their connections will appear here automatically.
            </div>
            <pre style={{ marginTop: 20, fontSize: 11, background: "var(--bg-elevated, #111827)", borderRadius: 8, padding: "14px 18px", textAlign: "left", color: "var(--text-muted, #9ca3af)", lineHeight: 1.7 }}>{`# Quick example — SQS → Lambda trigger
aws sqs create-queue --queue-name my-queue \\
  --endpoint-url http://localhost:4566

aws lambda create-function --function-name my-fn \\
  --runtime python3.11 --handler index.handler \\
  --role arn:aws:iam::000000000000:role/role \\
  --zip-file fileb://fn.zip \\
  --endpoint-url http://localhost:4566

aws lambda create-event-source-mapping \\
  --event-source-arn arn:aws:sqs:us-east-1:000000000000:my-queue \\
  --function-name my-fn \\
  --endpoint-url http://localhost:4566`}</pre>
          </div>
        )}

        {!loading && !isEmpty && (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelected(null)}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            style={{ background: "var(--bg-base, #0f1117)" }}
          >
            <Background color="#1e2530" variant={BackgroundVariant.Dots} gap={20} size={1} />
            <Controls style={{ background: "var(--bg-card, #1e2530)", border: "1px solid var(--border, #2d3748)", borderRadius: 8 }} />
            <MiniMap
              style={{ background: "var(--bg-card, #1e2530)", border: "1px solid var(--border, #2d3748)", borderRadius: 8 }}
              nodeColor={n => SVC_META[(n.data as { service: string }).service]?.color ?? "#6b7280"}
            />
            <Legend />
          </ReactFlow>
        )}

        <SidePanel node={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}
