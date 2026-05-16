const DRAWIO = process.env.DRAWIO_ENDPOINT ?? "http://ministack-drawio:8080";

export async function GET() {
  try {
    const r = await fetch(`${DRAWIO}/`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    return new Response(r.ok ? "ok" : "error", {
      status: r.ok ? 200 : 503,
    });
  } catch {
    return new Response("error", { status: 503 });
  }
}
