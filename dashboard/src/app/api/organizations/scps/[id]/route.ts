import { NextRequest, NextResponse } from "next/server";

const ENDPOINT = process.env.KUMOSTACK_ENDPOINT || "http://localhost:4566";

export async function PATCH(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await req.json();
  const res = await fetch(`${ENDPOINT}/_kumostack/organizations/scps/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(_req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const res = await fetch(`${ENDPOINT}/_kumostack/organizations/scps/${id}`, { method: "DELETE" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
