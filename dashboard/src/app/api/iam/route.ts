import { NextRequest, NextResponse } from "next/server";

const KS   = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";
const BASE = `${KS}/_kumostack/iam`;

// GET /api/iam?type=principals  → list all IAM users + roles
export async function GET(req: NextRequest) {
  const type = req.nextUrl.searchParams.get("type");
  try {
    const url = type === "principals" ? `${BASE}/principals` : `${BASE}/principals`;
    const r   = await fetch(url, { cache: "no-store" });
    return NextResponse.json(await r.json(), { status: r.status });
  } catch {
    return NextResponse.json({ principals: [] });
  }
}

// POST /api/iam  → simulate policy  { principal, actions, resource }
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const r    = await fetch(`${BASE}/simulate`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
      cache:   "no-store",
    });
    return NextResponse.json(await r.json(), { status: r.status });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
