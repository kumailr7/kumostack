const KUMOSTACK = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";
const BASE = `${KUMOSTACK}/_kumostack/chaos`;

export async function GET() {
  try {
    const res = await fetch(BASE, { cache: "no-store" });
    const data = await res.json();
    return Response.json(data);
  } catch {
    return Response.json({ rules: [] });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const res = await fetch(BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data);
  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const url = new URL(req.url);
    const id = url.searchParams.get("id");
    const endpoint = id ? `${BASE}/${id}` : BASE;
    const res = await fetch(endpoint, { method: "DELETE" });
    const data = await res.json();
    return Response.json(data);
  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500 });
  }
}

export async function PATCH(req: Request) {
  try {
    const url = new URL(req.url);
    const id = url.searchParams.get("id");
    if (!id) return Response.json({ error: "id required" }, { status: 400 });
    const body = await req.json();
    const res = await fetch(`${BASE}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data);
  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500 });
  }
}
