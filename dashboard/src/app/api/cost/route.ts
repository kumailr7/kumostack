import { NextResponse } from "next/server";

const KS = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";

export async function GET() {
  try {
    const r = await fetch(`${KS}/_kumostack/cost/report`, { cache: "no-store" });
    return NextResponse.json(await r.json(), { status: r.status });
  } catch {
    return NextResponse.json({ line_items: [], estimated_session_cost: 0, monthly_projection: 0, total_api_calls: 0, uptime_hours: 0 });
  }
}
