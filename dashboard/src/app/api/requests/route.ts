const MINISTACK = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";

export async function GET() {
  try {
    const r = await fetch(`${MINISTACK}/_kumostack/requests`, { cache: "no-store" });
    const data = await r.json();
    const list = Array.isArray(data) ? data : (data?.requests ?? []);
    return Response.json(list);
  } catch {
    return Response.json([], { status: 200 });
  }
}
