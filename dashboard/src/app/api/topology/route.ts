import { NextResponse } from "next/server";

const KS = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";

export async function GET() {
  try {
    const r = await fetch(`${KS}/_kumostack/topology`, { cache: "no-store" });
    return NextResponse.json(await r.json(), { status: r.status });
  } catch {
    return NextResponse.json({ nodes: [], edges: [] });
  }
}
