import { NextResponse } from "next/server";

const KS   = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";
const BASE = `${KS}/_kumostack/k6`;

async function proxy(url: string, init?: RequestInit) {
  const r = await fetch(url, { cache: "no-store", ...init });
  return NextResponse.json(await r.json().catch(() => ({})), { status: r.status });
}

// GET /api/k6          → job status
export async function GET() {
  try {
    return proxy(`${BASE}/status`);
  } catch {
    return NextResponse.json({ status: "idle" });
  }
}

// POST /api/k6         → start run   { scenario, vus, duration }
// POST /api/k6?stop=1  → stop run
export async function POST(req: Request) {
  const stop = new URL(req.url).searchParams.get("stop");
  try {
    if (stop) return proxy(`${BASE}/stop`, { method: "POST" });
    const body = await req.json().catch(() => ({}));
    return proxy(`${BASE}/run`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

// DELETE /api/k6       → cleanup exited container
export async function DELETE() {
  try {
    return proxy(`${BASE}/cleanup`, { method: "DELETE" });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
