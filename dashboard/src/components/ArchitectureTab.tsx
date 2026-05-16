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
  BackgroundVariant,
  MarkerType,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AwsServiceNode from "./nodes/AwsServiceNode";

const nodeTypes = { awsNode: AwsServiceNode };

const SERVICE_COLOR: Record<string, string> = {
  cloudfront: "#8C4FFF",
  s3: "#3F8624",
  ec2: "#F58536",
  alb: "#8C4FFF",
  rds: "#527FFF",
  lambda: "#F58536",
  dynamodb: "#527FFF",
  sqs: "#F58536",
  wafv2: "#DD344C",
  ecr: "#F58536",
  secretsmanager: "#DD344C",
};

const TIER_LABELS: Record<number, string> = {
  80:   "Security",
  320:  "CDN / Edge",
  560:  "Networking",
  800:  "Compute",
  1040: "Storage",
  1280: "Database",
  1520: "App Services",
};

export default function ArchitectureTab({ connected }: { connected: boolean }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [resourceCount, setResourceCount] = useState(0);

  const fetchArchitecture = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/architecture");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const styledEdges = (data.edges as Edge[]).map((e: Edge) => ({
        ...e,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed, color: "#334155" },
        style: { stroke: "#334155", strokeWidth: 2 },
        labelStyle: { fontSize: 9, fill: "#9aa1ad" },
        labelBgStyle: { fill: "#161a23" },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 3,
      }));

      setNodes(data.nodes as Node[]);
      setEdges(styledEdges);
      setResourceCount((data.nodes as Node[]).length);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    if (connected) {
      fetchArchitecture();
      const interval = setInterval(fetchArchitecture, 30_000);
      return () => clearInterval(interval);
    }
  }, [connected, fetchArchitecture]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const tiers = [...new Set(nodes.map((n) => n.position.x))].sort((a, b) => a - b);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)" }}>
      {/* Header */}
      <div className="tab-header" style={{ paddingBottom: 12, paddingTop: 12 }}>
        <h1>Architecture</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {resourceCount > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-dim)" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", display: "inline-block", boxShadow: "0 0 6px #22c55e" }} />
              {resourceCount} resource{resourceCount !== 1 ? "s" : ""}
            </div>
          )}
          {lastRefresh && (
            <span style={{ fontSize: 11, color: "var(--text-faint)" }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            className="btn btn-sm"
            onClick={fetchArchitecture}
            disabled={loading || !connected}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </div>

      {/* Tier column labels */}
      {!loading && nodes.length > 0 && (
        <div style={{ position: "relative", height: 24, background: "var(--bg-elevated)", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
          {tiers.map((x) => (
            <div
              key={x}
              style={{ position: "absolute", left: x - 10, width: 160, top: 4, textAlign: "center" }}
            >
              <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-faint)" }}>
                {TIER_LABELS[x] ?? ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Canvas */}
      <div style={{ flex: 1, position: "relative" }}>
        {/* Not connected */}
        {!connected && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: 12, padding: "32px 40px", textAlign: "center", maxWidth: 380 }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1" style={{ margin: "0 auto 12px" }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p style={{ color: "var(--text-dim)", fontWeight: 600, marginBottom: 6 }}>KumoStack is not connected</p>
              <p style={{ color: "var(--text-faint)", fontSize: 12 }}>Start KumoStack and the diagram will load automatically.</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {connected && error && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
            <div style={{ background: "var(--bg-card)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 12, padding: "32px 40px", textAlign: "center", maxWidth: 380 }}>
              <p style={{ color: "#f87171", fontWeight: 600, marginBottom: 6 }}>Cannot reach KumoStack API</p>
              <p style={{ color: "var(--text-faint)", fontSize: 12, marginBottom: 16 }}>{error}</p>
              <button className="btn btn-sm" onClick={fetchArchitecture}>Retry</button>
            </div>
          </div>
        )}

        {/* Empty state */}
        {connected && !error && !loading && nodes.length === 0 && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, padding: "40px 48px", textAlign: "center", maxWidth: 440 }}>
              <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="0.8" style={{ margin: "0 auto 16px" }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
              </svg>
              <p style={{ color: "var(--text)", fontWeight: 600, fontSize: 16, marginBottom: 8 }}>No resources found</p>
              <p style={{ color: "var(--text-faint)", fontSize: 13, lineHeight: 1.6 }}>
                Create AWS resources in KumoStack and they&apos;ll appear here automatically.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 20, justifyContent: "center" }}>
                {["S3 Bucket", "EC2 Instance", "RDS DB", "Lambda", "CloudFront", "ALB"].map((svc) => (
                  <span key={svc} style={{ padding: "3px 8px", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 11, color: "var(--text-dim)" }}>
                    {svc}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          style={{ background: "#0b0d12" }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1a1f2e" />
          <Controls
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: 8 }}
          />
          <MiniMap
            nodeColor={(node) => SERVICE_COLOR[(node.data as { service: string }).service] ?? "#4b5563"}
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-strong)", borderRadius: 8 }}
            maskColor="rgba(11,13,18,0.75)"
          />
        </ReactFlow>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", alignItems: "center", gap: 24, padding: "8px 24px", background: "var(--bg-elevated)", borderTop: "1px solid var(--border)", flexShrink: 0, overflowX: "auto" }}>
        <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-faint)", whiteSpace: "nowrap" }}>Legend</span>
        {[
          { color: "#DD344C", label: "Security" },
          { color: "#8C4FFF", label: "CDN / Networking" },
          { color: "#F58536", label: "Compute / Registry" },
          { color: "#3F8624", label: "Storage" },
          { color: "#527FFF", label: "Database" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />
            <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
