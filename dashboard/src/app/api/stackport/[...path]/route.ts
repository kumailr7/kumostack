// Transparent proxy to the Stackport backend.
// All /api/stackport/** requests are forwarded to http://kumostack-stackport:8080/api/**
// (Docker-internal) so the browser never needs to know about port 8082.

const SP = process.env.STACKPORT_ENDPOINT ?? "http://kumostack-stackport:8080";

async function proxy(req: Request, params: { path: string[] }) {
  const subpath = params.path.join("/");
  const incoming = new URL(req.url);
  const target   = `${SP}/api/${subpath}${incoming.search}`;

  const init: RequestInit = {
    method:  req.method,
    headers: { "Content-Type": "application/json" },
    cache:   "no-store",
  };

  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.text();
  }

  try {
    const res = await fetch(target, init);
    const body = await res.text();
    return new Response(body, {
      status:  res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json({ error: "Stackport unreachable" }, { status: 503 });
  }
}

export async function GET(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function POST(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function PUT(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function DELETE(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function PATCH(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
