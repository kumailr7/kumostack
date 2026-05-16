const BASE = `${process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566"}/_kumostack`;

export async function GET() {
  try {
    const r = await fetch(`${BASE}/state`, { cache: "no-store" });
    const data = await r.json();
    return Response.json(data);
  } catch {
    return Response.json([], { status: 200 });
  }
}

export async function POST(req: Request) {
  try {
    const { name } = await req.json();
    const r = await fetch(`${BASE}/state/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await r.json().catch(() => ({}));
    return Response.json(data, { status: r.status });
  } catch {
    return Response.json({ error: "failed" }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const name = searchParams.get("name") ?? "";
    const r = await fetch(`${BASE}/state/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    return Response.json({}, { status: r.ok ? 200 : r.status });
  } catch {
    return Response.json({ error: "failed" }, { status: 500 });
  }
}

export async function PATCH(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const name = searchParams.get("name") ?? "";
    const r = await fetch(`${BASE}/state/load`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    return Response.json({}, { status: r.ok ? 200 : r.status });
  } catch {
    return Response.json({ error: "failed" }, { status: 500 });
  }
}
