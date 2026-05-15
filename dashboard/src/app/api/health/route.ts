const MINISTACK = process.env.MINISTACK_ENDPOINT ?? "http://localhost:4566";

export async function GET() {
  try {
    const res = await fetch(`${MINISTACK}/_ministack/health`, {
      cache: "no-store",
    });
    const data = await res.json();
    return Response.json(data);
  } catch {
    return Response.json({ error: "not_running" }, { status: 503 });
  }
}
