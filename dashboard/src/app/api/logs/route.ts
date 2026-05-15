const MINISTACK = process.env.MINISTACK_ENDPOINT ?? "http://localhost:4566";

export async function GET() {
  try {
    const r = await fetch(`${MINISTACK}/_ministack/logs`, { cache: "no-store" });
    const text = await r.text();
    return new Response(text, { headers: { "Content-Type": "text/plain" } });
  } catch {
    return new Response("", { status: 200 });
  }
}
