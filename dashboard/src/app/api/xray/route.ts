import { NextRequest, NextResponse } from "next/server";

const KS = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";

async function proxy(url: string, init?: RequestInit) {
  const r = await fetch(url, { cache: "no-store", ...init });
  return NextResponse.json(await r.json().catch(() => ({})), { status: r.status });
}

// GET /api/xray?limit=50        → trace summaries list
// GET /api/xray?service=graph   → service graph
export async function GET(req: NextRequest) {
  const type  = req.nextUrl.searchParams.get("service");
  const limit = req.nextUrl.searchParams.get("limit") ?? "50";
  try {
    if (type === "graph") return proxy(`${KS}/_kumostack/xray/graph`);
    return proxy(`${KS}/_kumostack/xray/traces?limit=${limit}`);
  } catch {
    return NextResponse.json({ traces: [], total: 0 });
  }
}

// DELETE /api/xray  → clear all traces
export async function DELETE() {
  try {
    return proxy(`${KS}/_kumostack/xray/clear`, { method: "DELETE" });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
