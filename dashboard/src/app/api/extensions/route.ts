const MINISTACK = process.env.MINISTACK_ENDPOINT ?? "http://localhost:4566";

export async function GET() {
  try {
    const r = await fetch(`${MINISTACK}/_ministack/extensions`, { cache: "no-store" });
    const data = await r.json();
    return Response.json(data);
  } catch {
    return Response.json([], { status: 200 });
  }
}
