"use client";
import { Handle, Position } from "@xyflow/react";

interface NodeData {
  label: string;
  service: string;
  status: string;
  meta: Record<string, string>;
}

const SERVICE_CONFIG: Record<
  string,
  { color: string; bg: string; border: string; icon: React.ReactNode; category: string }
> = {
  cloudfront: {
    color: "#ffffff",
    bg: "#8C4FFF",
    border: "#6B2FE0",
    category: "CDN",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <circle cx="20" cy="20" r="13" stroke="white" strokeWidth="2" fill="none" />
        <ellipse cx="20" cy="20" rx="6" ry="13" stroke="white" strokeWidth="1.5" fill="none" />
        <line x1="7" y1="20" x2="33" y2="20" stroke="white" strokeWidth="1.5" />
        <line x1="9" y1="13" x2="31" y2="13" stroke="white" strokeWidth="1.2" />
        <line x1="9" y1="27" x2="31" y2="27" stroke="white" strokeWidth="1.2" />
      </svg>
    ),
  },
  s3: {
    color: "#ffffff",
    bg: "#3F8624",
    border: "#2d6219",
    category: "Storage",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <ellipse cx="20" cy="12" rx="12" ry="5" fill="rgba(255,255,255,0.3)" stroke="white" strokeWidth="1.5" />
        <rect x="8" y="12" width="24" height="16" fill="rgba(255,255,255,0.1)" />
        <ellipse cx="20" cy="28" rx="12" ry="5" fill="rgba(255,255,255,0.2)" stroke="white" strokeWidth="1.5" />
        <line x1="8" y1="12" x2="8" y2="28" stroke="white" strokeWidth="1.5" />
        <line x1="32" y1="12" x2="32" y2="28" stroke="white" strokeWidth="1.5" />
        <ellipse cx="20" cy="20" rx="12" ry="5" fill="none" stroke="white" strokeWidth="1.2" strokeDasharray="3 2" />
      </svg>
    ),
  },
  ec2: {
    color: "#ffffff",
    bg: "#F58536",
    border: "#d4681a",
    category: "Compute",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <rect x="8" y="8" width="24" height="24" rx="3" stroke="white" strokeWidth="1.8" fill="none" />
        <rect x="13" y="13" width="14" height="14" rx="2" fill="rgba(255,255,255,0.3)" stroke="white" strokeWidth="1.2" />
        <circle cx="20" cy="20" r="3" fill="white" />
        <line x1="20" y1="8" x2="20" y2="4" stroke="white" strokeWidth="1.5" />
        <line x1="20" y1="32" x2="20" y2="36" stroke="white" strokeWidth="1.5" />
        <line x1="8" y1="20" x2="4" y2="20" stroke="white" strokeWidth="1.5" />
        <line x1="32" y1="20" x2="36" y2="20" stroke="white" strokeWidth="1.5" />
      </svg>
    ),
  },
  alb: {
    color: "#ffffff",
    bg: "#8C4FFF",
    border: "#6B2FE0",
    category: "Networking",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <path d="M20 8 L34 20 L20 32 L6 20 Z" stroke="white" strokeWidth="1.8" fill="rgba(255,255,255,0.15)" />
        <circle cx="20" cy="14" r="2.5" fill="white" />
        <circle cx="14" cy="23" r="2.5" fill="white" />
        <circle cx="26" cy="23" r="2.5" fill="white" />
        <line x1="20" y1="16" x2="15" y2="21" stroke="white" strokeWidth="1.3" />
        <line x1="20" y1="16" x2="25" y2="21" stroke="white" strokeWidth="1.3" />
      </svg>
    ),
  },
  rds: {
    color: "#ffffff",
    bg: "#527FFF",
    border: "#2955e0",
    category: "Database",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <ellipse cx="20" cy="13" rx="12" ry="5" stroke="white" strokeWidth="1.8" fill="rgba(255,255,255,0.2)" />
        <ellipse cx="20" cy="27" rx="12" ry="5" stroke="white" strokeWidth="1.8" fill="rgba(255,255,255,0.1)" />
        <line x1="8" y1="13" x2="8" y2="27" stroke="white" strokeWidth="1.8" />
        <line x1="32" y1="13" x2="32" y2="27" stroke="white" strokeWidth="1.8" />
        <ellipse cx="20" cy="20" rx="12" ry="5" fill="none" stroke="white" strokeWidth="1.2" strokeDasharray="3 2" />
      </svg>
    ),
  },
  lambda: {
    color: "#ffffff",
    bg: "#F58536",
    border: "#d4681a",
    category: "Compute",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <rect x="6" y="6" width="28" height="28" rx="4" stroke="white" strokeWidth="1.8" fill="none" />
        <text x="20" y="27" textAnchor="middle" fill="white" fontSize="18" fontFamily="serif" fontWeight="bold">λ</text>
      </svg>
    ),
  },
  dynamodb: {
    color: "#ffffff",
    bg: "#527FFF",
    border: "#2955e0",
    category: "Database",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <ellipse cx="20" cy="11" rx="11" ry="4" stroke="white" strokeWidth="1.6" fill="rgba(255,255,255,0.2)" />
        <line x1="9" y1="11" x2="9" y2="29" stroke="white" strokeWidth="1.6" />
        <line x1="31" y1="11" x2="31" y2="29" stroke="white" strokeWidth="1.6" />
        <ellipse cx="20" cy="29" rx="11" ry="4" stroke="white" strokeWidth="1.6" fill="rgba(255,255,255,0.1)" />
        <ellipse cx="20" cy="20" rx="11" ry="4" fill="none" stroke="white" strokeWidth="1.2" strokeDasharray="2 2" />
        <line x1="15" y1="17" x2="25" y2="23" stroke="white" strokeWidth="1.5" />
        <line x1="25" y1="17" x2="15" y2="23" stroke="white" strokeWidth="1.5" />
      </svg>
    ),
  },
  sqs: {
    color: "#ffffff",
    bg: "#F58536",
    border: "#d4681a",
    category: "Messaging",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <rect x="6" y="13" width="28" height="14" rx="2" stroke="white" strokeWidth="1.8" fill="rgba(255,255,255,0.15)" />
        <circle cx="13" cy="20" r="2.5" fill="white" />
        <circle cx="20" cy="20" r="2.5" fill="white" />
        <circle cx="27" cy="20" r="2.5" fill="white" />
        <path d="M30 9 L34 13 L30 17" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <path d="M10 9 L6 13 L10 17" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      </svg>
    ),
  },
  wafv2: {
    color: "#ffffff",
    bg: "#DD344C",
    border: "#b02238",
    category: "Security",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <path d="M20 5 L33 10 L33 22 C33 29 27 35 20 37 C13 35 7 29 7 22 L7 10 Z" stroke="white" strokeWidth="1.8" fill="rgba(255,255,255,0.15)" />
        <path d="M20 13 L26 15.5 L26 22 C26 26 23.5 29 20 30.5 C16.5 29 14 26 14 22 L14 15.5 Z" fill="rgba(255,255,255,0.25)" stroke="white" strokeWidth="1.2" />
        <line x1="20" y1="19" x2="20" y2="26" stroke="white" strokeWidth="2" strokeLinecap="round" />
        <circle cx="20" cy="17" r="1.5" fill="white" />
      </svg>
    ),
  },
  ecr: {
    color: "#ffffff",
    bg: "#F58536",
    border: "#d4681a",
    category: "Registry",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <rect x="6" y="8" width="28" height="24" rx="3" stroke="white" strokeWidth="1.8" fill="none" />
        <rect x="10" y="12" width="20" height="5" rx="1.5" fill="rgba(255,255,255,0.25)" stroke="white" strokeWidth="1.2" />
        <rect x="10" y="20" width="20" height="5" rx="1.5" fill="rgba(255,255,255,0.15)" stroke="white" strokeWidth="1.2" />
        <circle cx="13" cy="14.5" r="1.2" fill="white" />
        <circle cx="13" cy="22.5" r="1.2" fill="white" />
      </svg>
    ),
  },
  secretsmanager: {
    color: "#ffffff",
    bg: "#DD344C",
    border: "#b02238",
    category: "Security",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
        <rect x="10" y="17" width="20" height="15" rx="3" stroke="white" strokeWidth="1.8" fill="rgba(255,255,255,0.15)" />
        <path d="M14 17 L14 13 C14 9.7 26 9.7 26 13 L26 17" stroke="white" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        <circle cx="20" cy="24" r="3" fill="white" />
        <line x1="20" y1="27" x2="20" y2="30" stroke="white" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
};

const STATUS_COLOR: Record<string, string> = {
  running: "#22c55e",
  available: "#22c55e",
  active: "#22c55e",
  Deployed: "#22c55e",
  stopped: "#ef4444",
  terminated: "#6b7280",
  pending: "#f59e0b",
  unknown: "#6b7280",
};

export default function AwsServiceNode({ data }: { data: NodeData }) {
  const cfg = SERVICE_CONFIG[data.service] ?? SERVICE_CONFIG["ec2"];
  const statusColor = STATUS_COLOR[data.status] ?? "#6b7280";

  return (
    <div
      className="relative flex flex-col items-center"
      style={{ width: 140 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: cfg.border }} />
      <Handle type="source" position={Position.Right} style={{ background: cfg.border }} />

      {/* Card */}
      <div
        className="w-full rounded-xl shadow-lg overflow-hidden"
        style={{ border: `2px solid ${cfg.border}` }}
      >
        {/* Header with icon */}
        <div
          className="flex flex-col items-center justify-center py-3 px-2 gap-1"
          style={{ background: cfg.bg }}
        >
          {cfg.icon}
          <span className="text-white text-[10px] font-semibold uppercase tracking-wider opacity-80">
            {cfg.category}
          </span>
        </div>

        {/* Body */}
        <div className="bg-white px-2 py-2">
          <p
            className="text-center font-semibold text-gray-800 leading-tight"
            style={{ fontSize: 11, wordBreak: "break-all" }}
          >
            {data.label}
          </p>
          {data.meta && Object.keys(data.meta).length > 0 && (
            <div className="mt-1 space-y-0.5">
              {Object.entries(data.meta)
                .slice(0, 2)
                .map(([k, v]) =>
                  v ? (
                    <p key={k} className="text-gray-500 text-center leading-tight" style={{ fontSize: 9 }}>
                      {v}
                    </p>
                  ) : null
                )}
            </div>
          )}
        </div>

        {/* Status bar */}
        <div
          className="flex items-center justify-center gap-1 py-1"
          style={{ background: "#f8fafc" }}
        >
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ background: statusColor, boxShadow: `0 0 4px ${statusColor}` }}
          />
          <span className="text-gray-500 capitalize" style={{ fontSize: 9 }}>
            {data.status}
          </span>
        </div>
      </div>
    </div>
  );
}
