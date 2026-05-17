import { NextRequest, NextResponse } from "next/server";

const ENDPOINT = process.env.KUMOSTACK_ENDPOINT || "http://localhost:4566";

export async function GET() {
  try {
    const res = await fetch(`${ENDPOINT}/_kumostack/organizations/scps`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ scps: [] });
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${ENDPOINT}/_kumostack/organizations/scps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
