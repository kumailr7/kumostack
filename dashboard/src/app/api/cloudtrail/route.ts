import { NextResponse } from "next/server";

const ENDPOINT = process.env.KUMOSTACK_ENDPOINT || "http://localhost:4566";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const service = searchParams.get("service") || "";
  const limit = searchParams.get("limit") || "200";

  const params = new URLSearchParams({ limit });
  if (service) params.set("service", service);

  try {
    const res = await fetch(`${ENDPOINT}/_kumostack/cloudtrail/events?${params}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ events: [] });
  }
}
