"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Image from "next/image";
import dynamic from "next/dynamic";

const ArchitectureTab = dynamic(
  () => import("../components/ArchitectureTab"),
  { ssr: false, loading: () => (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", color: "var(--text-faint)", fontSize: 13 }}>
      Loading diagram…
    </div>
  )}
);

const CDN = "https://icon.icepanel.io/AWS/svg";

interface Service {
  name: string;
  icon: string;
  badge: "free" | "real";
  badgeText?: string;
  healthKey?: string;
}

interface Section {
  label: string;
  services: Service[];
}

const COLUMNS: Section[][] = [
  [
    {
      label: "App Integration",
      services: [
        { name: "API Gateway",           icon: `${CDN}/App-Integration/API-Gateway.svg`,                  badge: "free", healthKey: "apigateway" },
        { name: "API Gateway v2",        icon: `${CDN}/App-Integration/API-Gateway.svg`,                  badge: "free", healthKey: "apigateway" },
        { name: "SQS",                   icon: `${CDN}/App-Integration/Simple-Queue-Service.svg`,         badge: "free", healthKey: "sqs" },
        { name: "SNS",                   icon: `${CDN}/App-Integration/Simple-Notification-Service.svg`,  badge: "free", healthKey: "sns" },
        { name: "Step Functions",        icon: `${CDN}/App-Integration/Step-Functions.svg`,               badge: "free", healthKey: "states" },
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
        { name: "Lambda",       icon: `${CDN}/Compute/Lambda.svg`,                                 badge: "free", healthKey: "lambda" },
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
        { name: "CloudFormation",          icon: `${CDN}/Management-Governance/CloudFormation.svg`,  badge: "free", healthKey: "cloudformation" },
        { name: "CloudWatch Logs",         icon: `${CDN}/Management-Governance/CloudWatch.svg`,      badge: "free", healthKey: "logs" },
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
        { name: "Secrets Manager",     icon: `${CDN}/Security-Identity-Compliance/Secrets-Manager.svg`,                badge: "free", healthKey: "secretsmanager" },
        { name: "KMS",                 icon: `${CDN}/Security-Identity-Compliance/Key-Management-Service.svg`,         badge: "free", healthKey: "kms" },
        { name: "Certificate Manager", icon: `${CDN}/Security-Identity-Compliance/Certificate-Manager.svg`,            badge: "free", healthKey: "acm" },
        { name: "WAF v2",              icon: `${CDN}/Security-Identity-Compliance/WAF.svg`,                            badge: "free", healthKey: "wafv2" },
      ],
    },
    {
      label: "Storage",
      services: [
        { name: "S3",       icon: `${CDN}/Storage/Simple-Storage-Service.svg`, badge: "free", healthKey: "s3" },
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
        { name: "DynamoDB",     icon: `${CDN}/Database/DynamoDB.svg`,            badge: "free", healthKey: "dynamodb" },
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
        { name: "Kinesis",       icon: `${CDN}/Analytics/Kinesis.svg`,          badge: "free", healthKey: "kinesis" },
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

const TABS = ["Overview", "Status", "Resource Browser", "State", "App Inspector", "Logs", "Extensions", "Architecture"];
const REGIONS = ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1"];

type ServiceStatus = Record<string, string>;

function statusDotClass(status: string | undefined): string {
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
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function DisconnectedNotice() {
  return (
    <div className="notice">
      <WarnIcon />
      <div>
        MiniStack is not connected. Run{" "}
        <span className="mono" style={{ background: "rgba(0,0,0,0.3)", padding: "1px 6px", borderRadius: 3 }}>
          docker run -p 4566:4566 ministackorg/ministack
        </span>{" "}
        to start it.
      </div>
    </div>
  );
}

// ─── Overview Tab ───────────────────────────────────────────────────────────

function OverviewTab({ connected, serviceStatus, version }: {
  connected: boolean;
  serviceStatus: ServiceStatus;
  version: string | null;
}) {
  const allServices = COLUMNS.flat().flatMap((s) => s.services);
  const keys = [...new Set(allServices.map((s) => s.healthKey).filter(Boolean) as string[])];
  const healthy = keys.filter((k) => ["available", "running"].includes(serviceStatus[k] ?? "")).length;
  const errors = keys.filter((k) => serviceStatus[k] === "error").length;

  const [grafanaInput, setGrafanaInput] = useState("http://localhost:3002");
  const [grafanaUrl, setGrafanaUrl] = useState("http://localhost:3002");
  const [showGrafana, setShowGrafana] = useState(false);

  const [vectorInput, setVectorInput] = useState("http://localhost:8686");
  const [vectorUrl, setVectorUrl] = useState("http://localhost:8686");
  const [vectorHealth, setVectorHealth] = useState<"unknown" | "ok" | "error">("unknown");

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

  function applyGrafana() {
    setGrafanaUrl(grafanaInput);
    localStorage.setItem("grafanaUrl", grafanaInput);
  }

  function applyVector() {
    setVectorUrl(vectorInput);
    localStorage.setItem("vectorUrl", vectorInput);
  }

  return (
    <div>
      <div className="tab-header">
        <h1>Overview</h1>
        {version && <span className="version-badge">v{version}</span>}
      </div>

      <div className="stat-cards">
        <div className="stat-card">
          <div className="stat-value">{connected ? keys.length : "—"}</div>
          <div className="stat-label">Total Services</div>
        </div>
        <div className={`stat-card ${connected && healthy > 0 ? "stat-card--green" : ""}`}>
          <div className="stat-value">{connected ? healthy : "—"}</div>
          <div className="stat-label">Healthy</div>
        </div>
        <div className={`stat-card ${connected && errors > 0 ? "stat-card--red" : ""}`}>
          <div className="stat-value">{connected ? errors : "—"}</div>
          <div className="stat-label">Errors</div>
        </div>
        <div className={`stat-card ${connected ? "stat-card--green" : "stat-card--red"}`}>
          <div className="stat-value">{connected ? "Online" : "Offline"}</div>
          <div className="stat-label">MiniStack</div>
        </div>
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
            <input
              className="integration-input"
              value={grafanaInput}
              onChange={(e) => setGrafanaInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyGrafana()}
              placeholder="http://localhost:3000"
            />
            <button className="btn btn-sm" onClick={applyGrafana}>Apply</button>
            <button className="btn btn-sm btn-primary" onClick={() => setShowGrafana(!showGrafana)}>
              {showGrafana ? "Hide" : "Embed Dashboard"}
            </button>
            <a href={grafanaUrl} target="_blank" rel="noreferrer" className="btn btn-sm">Open ↗</a>
          </div>
        </div>
        {showGrafana ? (
          <iframe src={grafanaUrl} className="grafana-iframe" title="Grafana Dashboard" />
        ) : (
          <p className="integration-desc">
            Embed any Grafana dashboard to monitor MiniStack resources. Configure your Grafana URL above and click &quot;Embed Dashboard&quot;, or open it in a new tab.
          </p>
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
            <input
              className="integration-input"
              value={vectorInput}
              onChange={(e) => setVectorInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyVector()}
              placeholder="http://localhost:8686"
            />
            <button className="btn btn-sm" onClick={applyVector}>Apply</button>
          </div>
        </div>
        <p className="integration-desc">
          Route MiniStack logs through Vector for filtering, enrichment, and forwarding to any sink.
          Start Vector with <code className="inline-code">vector --config vector.toml</code> — see the Logs tab for a sample config.
        </p>
      </div>
    </div>
  );
}

// ─── Status Tab ─────────────────────────────────────────────────────────────

function StatusTab({ connected, serviceStatus }: { connected: boolean; serviceStatus: ServiceStatus }) {
  const [filter, setFilter] = useState<"all" | "running" | "error" | "idle">("all");

  const rows = COLUMNS.flat().flatMap((section) =>
    section.services.map((s) => ({ ...s, category: section.label }))
  );

  const filtered = rows.filter((s) => {
    const st = s.healthKey ? serviceStatus[s.healthKey] : undefined;
    if (filter === "running") return st === "available" || st === "running";
    if (filter === "error")   return st === "error";
    if (filter === "idle")    return !st || (st !== "available" && st !== "running" && st !== "error");
    return true;
  });

  return (
    <div>
      <div className="tab-header">
        <h1>Service Status</h1>
        <div className="filter-pills">
          {(["all", "running", "error", "idle"] as const).map((f) => (
            <button key={f} className={`pill-btn ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {!connected && <DisconnectedNotice />}

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Category</th>
              <th>Health Key</th>
              <th>Status</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => {
              const status = s.healthKey ? serviceStatus[s.healthKey] : undefined;
              return (
                <tr key={s.name + s.category}>
                  <td>
                    <div className="cell-with-icon">
                      <Image src={s.icon} alt={s.name} width={20} height={20} unoptimized />
                      <span>{s.name}</span>
                    </div>
                  </td>
                  <td className="td-dim">{s.category}</td>
                  <td className="td-mono">{s.healthKey ?? "—"}</td>
                  <td><StatusPill status={connected ? status : undefined} /></td>
                  <td>
                    <span className={`badge ${s.badge}`}>
                      {s.badgeText ?? (s.badge === "free" ? "Free" : "")}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Resource Browser Tab ────────────────────────────────────────────────────

function ResourceBrowserTab({ connected, serviceStatus, query, setQuery, region, setRegion }: {
  connected: boolean;
  serviceStatus: ServiceStatus;
  query: string;
  setQuery: (v: string) => void;
  region: string;
  setRegion: (v: string) => void;
}) {
  const q = query.trim().toLowerCase();

  return (
    <>
      <div className="header-row">
        <h1>Resource Browser</h1>
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
        <input
          className="search"
          placeholder="Which service are you looking for?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="columns">
        {COLUMNS.map((col, ci) => {
          const visible = col.filter((section) =>
            !q || section.services.some((s) => s.name.toLowerCase().includes(q))
          );
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
                          <a
                            key={s.name}
                            className="service"
                            onClick={() => alert(`Open resource view for: ${s.name}`)}
                          >
                            <div className="service-icon-wrap">
                              <div className="service-icon">
                                <Image src={s.icon} alt={s.name} width={32} height={32} unoptimized />
                              </div>
                              {connected && status && (
                                <span className={statusDotClass(status)} title={status} />
                              )}
                            </div>
                            <div className="service-name">{s.name}</div>
                            <span className={`badge ${s.badge}`}>
                              {s.badgeText ?? (s.badge === "free" ? "Free" : "")}
                            </span>
                          </a>
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

      <div className="footer">
        <div>MiniStack v0.x · MIT License · <span className="mono">port 4566</span></div>
        <div>
          <a href="https://ministack.org" target="_blank" rel="noreferrer">ministack.org</a>
          {" · "}
          <a href="https://github.com/ministackorg/ministack" target="_blank" rel="noreferrer">GitHub</a>
          {" · "}
          <a href="https://hub.docker.com/r/ministackorg/ministack" target="_blank" rel="noreferrer">Docker Hub</a>
        </div>
      </div>
    </>
  );
}

// ─── State Tab ───────────────────────────────────────────────────────────────

interface Snapshot { name: string; timestamp: string }

function StateTab({ connected }: { connected: boolean }) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [flash, setFlash] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/state")
      .then((r) => r.json())
      .then((d) => { setSnapshots(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => { setSnapshots([]); setLoading(false); });
  }, []);

  useEffect(() => { if (connected) load(); }, [connected, load]);

  function notify(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(""), 3000);
  }

  async function save() {
    const name = prompt("Snapshot name:", `snapshot-${Date.now()}`);
    if (!name) return;
    const r = await fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    notify(r.ok ? "Snapshot saved." : "Failed to save.");
    if (r.ok) load();
  }

  async function remove(name: string) {
    if (!confirm(`Delete "${name}"?`)) return;
    const r = await fetch(`/api/state?name=${encodeURIComponent(name)}`, { method: "DELETE" });
    notify(r.ok ? "Deleted." : "Failed to delete.");
    if (r.ok) load();
  }

  async function restore(name: string) {
    const r = await fetch(`/api/state?name=${encodeURIComponent(name)}`, { method: "PATCH" });
    notify(r.ok ? `Restored "${name}".` : "Failed to restore.");
  }

  return (
    <div>
      <div className="tab-header">
        <h1>State</h1>
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
          {!loading && snapshots.length === 0 && (
            <div className="empty-state">
              No snapshots yet. Click <strong>Save Snapshot</strong> to persist the current MiniStack state.
            </div>
          )}
          {snapshots.map((s) => (
            <div key={s.name} className="list-item">
              <div>
                <div className="item-title">{s.name}</div>
                <div className="item-sub">{s.timestamp}</div>
              </div>
              <div className="item-actions">
                <button className="btn btn-sm btn-primary" onClick={() => restore(s.name)}>Restore</button>
                <button className="btn btn-sm btn-danger" onClick={() => remove(s.name)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── App Inspector Tab ───────────────────────────────────────────────────────

interface ApiRequest {
  id: string;
  method: string;
  service: string;
  path: string;
  status: number;
  duration_ms: number;
  timestamp: string;
}

function AppInspectorTab({ connected }: { connected: boolean }) {
  const [requests, setRequests] = useState<ApiRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [live, setLive] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/requests")
      .then((r) => r.json())
      .then((d) => { setRequests(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => { setRequests([]); setLoading(false); });
  }, []);

  useEffect(() => { if (connected) load(); }, [connected, load]);

  useEffect(() => {
    if (!live || !connected) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [live, connected, load]);

  return (
    <div>
      <div className="tab-header">
        <h1>App Inspector</h1>
        <div className="tab-actions">
          <button className={`btn btn-sm ${live ? "btn-primary" : ""}`} onClick={() => setLive(!live)}>
            {live ? "⏸ Pause" : "▶ Live"}
          </button>
          <button className="btn btn-sm" onClick={load} disabled={!connected}>Refresh</button>
          <button className="btn btn-sm btn-danger" onClick={() => setRequests([])}>Clear</button>
        </div>
      </div>

      {!connected && <DisconnectedNotice />}

      {connected && (
        <div className="table-wrap">
          {loading && requests.length === 0 && <div className="empty-state">Loading…</div>}
          {!loading && requests.length === 0 && (
            <div className="empty-state">
              No API requests captured yet. Make calls to MiniStack and they will appear here.
            </div>
          )}
          {requests.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Service</th>
                  <th>Path</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Time</th>
                </tr>
              </thead>
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

// ─── Logs Tab ────────────────────────────────────────────────────────────────

function LogsTab({ connected }: { connected: boolean }) {
  const [source, setSource] = useState<"ministack" | "vector">("ministack");
  const [logs, setLogs] = useState<string[]>([]);
  const [live, setLive] = useState(false);
  const [vectorUrl, setVectorUrl] = useState("http://localhost:8686");
  const [vectorHealth, setVectorHealth] = useState<"unknown" | "ok" | "error">("unknown");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = localStorage.getItem("vectorUrl");
    if (stored) setVectorUrl(stored);
  }, []);

  useEffect(() => {
    fetch(`/api/vector?base=${encodeURIComponent(vectorUrl)}&path=/health`)
      .then((r) => setVectorHealth(r.ok ? "ok" : "error"))
      .catch(() => setVectorHealth("error"));
  }, [vectorUrl]);

  const fetchLogs = useCallback(() => {
    const url = source === "ministack"
      ? "/api/logs"
      : `/api/vector?base=${encodeURIComponent(vectorUrl)}&path=/components`;
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        const lines = text.split("\n").filter(Boolean);
        setLogs((prev) => [...prev, ...lines].slice(-1000));
      })
      .catch(() => {});
  }, [source, vectorUrl]);

  useEffect(() => { fetchLogs(); }, [source]);

  useEffect(() => {
    if (!live) return;
    const id = setInterval(fetchLogs, 2000);
    return () => clearInterval(id);
  }, [live, fetchLogs]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  const VECTOR_CONFIG = `# vector.toml — sample MiniStack integration
[api]
enabled = true
address = "0.0.0.0:8686"

[sources.ministack_health]
type = "http_client"
endpoint = "http://localhost:4566/_localstack/health"
scrape_interval_secs = 10
method = "GET"

[transforms.annotate]
type = "remap"
inputs = ["ministack_health"]
source = """
  .timestamp = now()
  .source = "ministack"
"""

[sinks.stdout]
type = "console"
inputs = ["annotate"]
encoding.codec = "json"`;

  return (
    <div>
      <div className="tab-header">
        <h1>Logs</h1>
        <div className="tab-actions">
          <div className="filter-pills">
            <button className={`pill-btn ${source === "ministack" ? "active" : ""}`} onClick={() => { setSource("ministack"); setLogs([]); }}>
              MiniStack
            </button>
            <button className={`pill-btn ${source === "vector" ? "active" : ""}`} onClick={() => { setSource("vector"); setLogs([]); }}>
              Vector.dev
              {source === "vector" && (
                <span className={`dot-indicator ${vectorHealth === "ok" ? "dot--green" : "dot--red"}`} />
              )}
            </button>
          </div>
          <button className={`btn btn-sm ${live ? "btn-primary" : ""}`} onClick={() => setLive(!live)}>
            {live ? "⏸ Pause" : "▶ Live"}
          </button>
          <button className="btn btn-sm" onClick={fetchLogs}>Refresh</button>
          <button className="btn btn-sm btn-danger" onClick={() => setLogs([])}>Clear</button>
        </div>
      </div>

      {source === "vector" && (
        <div className="integration-card" style={{ marginBottom: 16 }}>
          <div className="integration-card-header">
            <div className="integration-card-title">
              <span>Vector API endpoint</span>
              <span className={`pill ${vectorHealth === "ok" ? "pill--green" : "pill--red"}`}>
                {vectorHealth === "ok" ? "Connected" : "Not running"}
              </span>
            </div>
            <div className="integration-actions">
              <input
                className="integration-input"
                value={vectorUrl}
                onChange={(e) => {
                  setVectorUrl(e.target.value);
                  localStorage.setItem("vectorUrl", e.target.value);
                }}
                placeholder="http://localhost:8686"
              />
            </div>
          </div>
          <details className="collapsible">
            <summary>Sample vector.toml config</summary>
            <pre className="code-snippet">{VECTOR_CONFIG}</pre>
          </details>
        </div>
      )}

      <div className="log-viewer" ref={scrollRef}>
        {logs.length === 0 ? (
          <div className="log-empty">
            {source === "vector" && vectorHealth === "error"
              ? "Vector is not running. Start it with: vector --config vector.toml"
              : "No logs yet. Click Refresh or enable Live mode."}
          </div>
        ) : (
          logs.map((line, i) => (
            <div key={i} className={`log-line ${line.includes("ERROR") || line.includes("error") ? "log-line--error" : line.includes("WARN") ? "log-line--warn" : ""}`}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Extensions Tab ──────────────────────────────────────────────────────────

interface DockerConfig {
  image: string;
  containerName: string;
  ports: { host: number; container: number }[];
  uiUrl?: string;        // opens in browser when running
  healthPath?: string;   // appended to uiUrl for health check
  env?: Record<string, string>;
}

interface ExtensionDef {
  name: string;
  pkg: string;
  description: string;
  tags: string[];
  repo: string;
  docker?: DockerConfig; // present = can launch standalone via Docker
}

const EXTENSION_CATALOG: ExtensionDef[] = [
  {
    name: "MailHog",
    pkg: "localstack-extension-mailhog",
    description: "Captures outgoing SMTP emails and shows them in a web UI. Connect your app's SES or SMTP client to port 1025 and inspect every message.",
    tags: ["Email", "Testing"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/mailhog",
    docker: {
      image: "mailhog/mailhog:latest",
      containerName: "ministack-mailhog",
      ports: [{ host: 1025, container: 1025 }, { host: 8025, container: 8025 }],
      uiUrl: "http://localhost:8025",
      healthPath: "/",
    },
  },
  {
    name: "WireMock",
    pkg: "localstack-wiremock",
    description: "Stub any HTTP API with flexible request matching and response templating. Perfect for mocking third-party services your app depends on.",
    tags: ["Mocking", "HTTP"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/wiremock",
    docker: {
      image: "wiremock/wiremock:latest",
      containerName: "ministack-wiremock",
      ports: [{ host: 8088, container: 8080 }],
      uiUrl: "http://localhost:8088/__admin/",
      healthPath: "__admin/health",
    },
  },
  {
    name: "Stripe Mock",
    pkg: "localstack-extension-stripe",
    description: "Full Stripe API mock — create charges, customers, subscriptions, and webhooks locally without touching the real Stripe sandbox.",
    tags: ["Payments", "Mock"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/stripe",
    docker: {
      image: "stripe/stripe-mock:latest",
      containerName: "ministack-stripe",
      ports: [{ host: 12111, container: 12111 }],
      uiUrl: "http://localhost:12111",
    },
  },
  {
    name: "httpbin",
    pkg: "localstack-extension-httpbin",
    description: "HTTP request & response testing service. Inspect headers, query params, redirects, delays and more — great for debugging HTTP clients.",
    tags: ["HTTP", "Testing"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/httpbin",
    docker: {
      image: "kennethreitz/httpbin:latest",
      containerName: "ministack-httpbin",
      ports: [{ host: 8083, container: 80 }],
      uiUrl: "http://localhost:8083",
      healthPath: "/get",
    },
  },
  {
    name: "TypeDB",
    pkg: "localstack-extension-typedb",
    description: "Polymorphic database for complex domain modelling. Run knowledge-graph queries over your data using TypeQL alongside your AWS services.",
    tags: ["Database", "Graph"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/typedb",
    docker: {
      image: "vaticle/typedb:latest",
      containerName: "ministack-typedb",
      ports: [{ host: 1729, container: 1729 }],
    },
  },
  {
    name: "ParadeDB",
    pkg: "localstack-extension-paradedb",
    description: "PostgreSQL with built-in full-text and vector search. Drop-in Elasticsearch replacement that speaks SQL — connect on port 5435.",
    tags: ["Database", "Search"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/paradedb",
    docker: {
      image: "paradedb/paradedb:latest",
      containerName: "ministack-paradedb",
      ports: [{ host: 5435, container: 5432 }],
      env: { POSTGRESQL_PASSWORD: "ministack", POSTGRESQL_USERNAME: "ministack", POSTGRESQL_DATABASE: "ministack" },
    },
  },
  // Pro-only extensions — no standalone Docker image
  {
    name: "Miniflare",
    pkg: "localstack-extension-miniflare",
    description: "Emulate Cloudflare Workers locally alongside your AWS services. Useful for edge + cloud hybrid architectures.",
    tags: ["Cloudflare", "Edge"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/miniflare",
  },
  {
    name: "AWS Proxy",
    pkg: "localstack-extension-aws-proxy",
    description: "Transparently proxies specific AWS service calls to real AWS while keeping the rest local. Ideal for hybrid testing scenarios.",
    tags: ["Proxy", "AWS"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/aws-proxy",
  },
  {
    name: "Terraform Init",
    pkg: "localstack-extension-terraform-init",
    description: "Automatically initialises Terraform providers when LocalStack starts, reducing cold-start friction in IaC workflows.",
    tags: ["IaC", "Terraform"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/terraform-init",
  },
  {
    name: "Diagnosis Viewer",
    pkg: "localstack-extension-diagnosis-viewer",
    description: "Diagnostic dashboard inside LocalStack for inspecting service state, logs, and configuration issues in one place.",
    tags: ["Debugging", "Observability"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/diagnosis-viewer",
  },
  {
    name: "Hello World",
    pkg: "localstack-extension-hello-world",
    description: "Minimal reference extension showing how to scaffold a custom LocalStack extension. Start here when building your own.",
    tags: ["Example", "Dev"],
    repo: "https://github.com/localstack/localstack-extensions/tree/main/hello-world",
  },
];

const TAG_COLORS: Record<string, string> = {
  Email: "#60a5fa", Testing: "#a78bfa", HTTP: "#34d399", Mocking: "#f472b6",
  Payments: "#fbbf24", Mock: "#f472b6", Cloudflare: "#fb923c", Edge: "#fb923c",
  IaC: "#4ade80", Terraform: "#4ade80", Proxy: "#60a5fa", AWS: "#f59e0b",
  Debugging: "#e879f9", Observability: "#e879f9", Database: "#38bdf8",
  Graph: "#38bdf8", Search: "#38bdf8", Example: "#9ca3af", Dev: "#9ca3af",
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }
  return (
    <button className="copy-btn" onClick={copy} title="Copy to clipboard">
      {copied ? (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

// per-card hook that manages launch/stop for one extension
function useExtensionDocker(ext: ExtensionDef) {
  const [status, setStatus] = useState<"unknown" | "running" | "stopped" | "starting" | "stopping">("unknown");
  const [error, setError] = useState("");

  const check = useCallback(async () => {
    if (!ext.docker) return;
    const r = await fetch(`/api/extensions/docker?name=${ext.docker.containerName}`).catch(() => null);
    if (!r) return;
    const d = await r.json().catch(() => null);
    setStatus(d?.running ? "running" : "stopped");
  }, [ext.docker]);

  useEffect(() => { check(); }, [check]);

  async function launch() {
    if (!ext.docker) return;
    setStatus("starting");
    setError("");
    const r = await fetch("/api/extensions/docker", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ext.docker),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { setError(d.error ?? "Failed to launch"); setStatus("stopped"); }
    else { setTimeout(check, 1500); }
  }

  async function stop() {
    if (!ext.docker) return;
    setStatus("stopping");
    setError("");
    const r = await fetch(`/api/extensions/docker?name=${ext.docker.containerName}`, { method: "DELETE" });
    if (!r.ok) { const d = await r.json().catch(() => ({})); setError(d.error ?? "Failed to stop"); }
    setTimeout(check, 1000);
  }

  return { status, error, launch, stop, refresh: check };
}

function ExtensionCard({ ext }: { ext: ExtensionDef }) {
  const { status, error, launch, stop } = useExtensionDocker(ext);
  const isRunning = status === "running";
  const isBusy = status === "starting" || status === "stopping";

  return (
    <div className={`ext-card ${isRunning ? "ext-card--running" : ""}`}>
      <div className="ext-card-header">
        <div className="ext-card-name">{ext.name}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {ext.docker ? (
            <span className={`pill ${isRunning ? "pill--green" : status === "unknown" ? "pill--dim" : "pill--dim"}`}>
              {status === "starting" ? "Starting…" : status === "stopping" ? "Stopping…" : isRunning ? "Running" : "Docker"}
            </span>
          ) : (
            <span className="ext-pro-badge">Pro only</span>
          )}
        </div>
      </div>

      <p className="ext-card-desc">{ext.description}</p>

      <div className="ext-card-tags">
        {ext.tags.map((t) => (
          <span key={t} className="ext-tag" style={{ color: TAG_COLORS[t] ?? "var(--text-dim)", borderColor: `${TAG_COLORS[t] ?? "var(--border-strong)"}40` }}>
            {t}
          </span>
        ))}
      </div>

      {ext.docker && (
        <div className="ext-ports">
          {ext.docker.ports.map((p) => (
            <span key={p.host} className="ext-port-chip">:{p.host}</span>
          ))}
        </div>
      )}

      {error && <div className="ext-error">{error}</div>}

      <div className="ext-card-footer">
        {ext.docker ? (
          <div className="ext-actions">
            {isRunning ? (
              <>
                {ext.docker.uiUrl && (
                  <a href={ext.docker.uiUrl} target="_blank" rel="noreferrer" className="btn btn-sm btn-primary">
                    Open UI ↗
                  </a>
                )}
                <button className="btn btn-sm btn-danger" onClick={stop} disabled={isBusy}>Stop</button>
              </>
            ) : (
              <button className="btn btn-sm btn-primary" onClick={launch} disabled={isBusy}>
                {status === "starting" ? "Launching…" : "Launch"}
              </button>
            )}
            <div className="ext-image-name">
              <code className="ext-install-cmd">{ext.docker.image}</code>
              <CopyButton text={`docker run -d --name ${ext.docker.containerName} ${ext.docker.ports.map((p) => `-p ${p.host}:${p.container}`).join(" ")} ${ext.docker.image}`} />
            </div>
          </div>
        ) : (
          <div className="ext-install-row">
            <code className="ext-install-cmd">localstack extensions install {ext.pkg}</code>
            <CopyButton text={`localstack extensions install ${ext.pkg}`} />
          </div>
        )}
        <a href={ext.repo} target="_blank" rel="noreferrer" className="ext-repo-link">source ↗</a>
      </div>
    </div>
  );
}

function ExtensionsTab() {
  const [search, setSearch] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [view, setView] = useState<"all" | "docker" | "pro">("all");

  const allTags = [...new Set(EXTENSION_CATALOG.flatMap((e) => e.tags))].sort();

  const visible = EXTENSION_CATALOG.filter((e) => {
    const q = search.trim().toLowerCase();
    const matchSearch = !q || e.name.toLowerCase().includes(q) || e.description.toLowerCase().includes(q) || e.tags.some((t) => t.toLowerCase().includes(q));
    const matchTag = !activeTag || e.tags.includes(activeTag);
    const matchView = view === "all" || (view === "docker" && !!e.docker) || (view === "pro" && !e.docker);
    return matchSearch && matchTag && matchView;
  });

  return (
    <div>
      <div className="tab-header">
        <h1>Extensions</h1>
        <div className="tab-actions">
          <a href="https://github.com/localstack/localstack-extensions" target="_blank" rel="noreferrer" className="btn btn-sm">GitHub ↗</a>
        </div>
      </div>

      <div className="ext-legend">
        <div className="ext-legend-item">
          <span className="pill pill--green" style={{ fontSize: 11 }}>Docker</span>
          Runs as a standalone Docker container — no LocalStack Pro needed. Launch directly from this dashboard.
        </div>
        <div className="ext-legend-item">
          <span className="ext-pro-badge">Pro only</span>
          Requires LocalStack Pro — integrates into the LocalStack runtime. Install with the CLI command shown.
        </div>
      </div>

      <div className="ext-toolbar">
        <input
          className="search"
          style={{ flex: 1, marginBottom: 0 }}
          placeholder="Search extensions…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filter-pills">
          {(["all", "docker", "pro"] as const).map((v) => (
            <button key={v} className={`pill-btn ${view === v ? "active" : ""}`} onClick={() => setView(v)}>
              {v === "all" ? "All" : v === "docker" ? "Docker (free)" : "Pro only"}
            </button>
          ))}
        </div>
      </div>

      {activeTag && (
        <div className="filter-pills" style={{ marginBottom: 16, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, color: "var(--text-faint)", marginRight: 4 }}>Tag:</span>
          {allTags.map((t) => (
            <button
              key={t}
              className={`pill-btn ${activeTag === t ? "active" : ""}`}
              onClick={() => setActiveTag(activeTag === t ? null : t)}
              style={activeTag === t ? { borderColor: TAG_COLORS[t] ?? "var(--accent)", color: TAG_COLORS[t] ?? "var(--accent)" } : {}}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      {!activeTag && (
        <div className="filter-pills" style={{ marginBottom: 20, flexWrap: "wrap" }}>
          {allTags.map((t) => (
            <button
              key={t}
              className="pill-btn"
              onClick={() => setActiveTag(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      <div className="ext-grid">
        {visible.map((ext) => <ExtensionCard key={ext.pkg} ext={ext} />)}
      </div>

      {visible.length === 0 && <div className="empty-state">No extensions match your search.</div>}
    </div>
  );
}

// ─── Root ────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("Overview");
  const [region, setRegion] = useState("us-east-1");
  const [query, setQuery] = useState("");
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({});
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    const poll = () => {
      fetch("/api/health")
        .then((r) => r.json())
        .then((data) => {
          if (data.services) {
            setConnected(true);
            setServiceStatus(data.services);
            if (data.version) setVersion(data.version);
          } else {
            setConnected(false);
          }
        })
        .catch(() => setConnected(false));
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <div className="topbar">
        <div className="endpoint">
          <span className={`status-dot${connected ? " connected" : ""}`} />
          <span>localhost.ministack.org:4566</span>
          {connected && version && <span className="version-badge">v{version}</span>}
          <span className="endpoint-menu">•••</span>
        </div>
        <div className="tabs">
          {TABS.map((tab) => (
            <div
              key={tab}
              className={`tab${activeTab === tab ? " active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </div>
          ))}
        </div>
      </div>

      <div className="main">
        {activeTab === "Overview" && (
          <OverviewTab connected={connected} serviceStatus={serviceStatus} version={version} />
        )}
        {activeTab === "Status" && (
          <StatusTab connected={connected} serviceStatus={serviceStatus} />
        )}
        {activeTab === "Resource Browser" && (
          <ResourceBrowserTab
            connected={connected}
            serviceStatus={serviceStatus}
            query={query}
            setQuery={setQuery}
            region={region}
            setRegion={setRegion}
          />
        )}
        {activeTab === "State" && <StateTab connected={connected} />}
        {activeTab === "App Inspector" && <AppInspectorTab connected={connected} />}
        {activeTab === "Logs" && <LogsTab connected={connected} />}
        {activeTab === "Extensions" && <ExtensionsTab />}
        {activeTab === "Architecture" && <ArchitectureTab connected={connected} />}
      </div>
    </>
  );
}
