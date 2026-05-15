export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const base = searchParams.get("base") ?? "http://localhost:8686";
  const path = searchParams.get("path") ?? "/health";

  // Only allow localhost/private addresses to prevent SSRF
  const url = new URL(path, base);
  const hostname = url.hostname;
  const isLocal =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1" ||
    hostname.startsWith("192.168.") ||
    hostname.startsWith("10.") ||
    hostname.startsWith("172.");

  if (!isLocal) {
    return Response.json({ error: "Only local addresses allowed" }, { status: 403 });
  }

  try {
    const r = await fetch(url.toString(), { cache: "no-store" });
    const text = await r.text();
    return new Response(text, {
      status: r.status,
      headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json({ error: "vector_unreachable" }, { status: 503 });
  }
}
