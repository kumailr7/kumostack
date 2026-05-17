import { NextResponse } from "next/server";

const ENDPOINT = process.env.KUMOSTACK_ENDPOINT || "http://localhost:4566";

export async function GET() {
  try {
    const res = await fetch(`${ENDPOINT}/_kumostack/sts/assume-role-log`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ log: [] });
  }
}
