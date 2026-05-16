const KS = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";
const BASE = `${KS}/_kumostack/chaos`;

async function proxy(url: string, init?: RequestInit) {
  const r = await fetch(url, { cache: "no-store", ...init });
  return Response.json(await r.json().catch(() => ({})), { status: r.status });
}

// GET  /api/chaos            → list fault rules
// GET  /api/chaos?type=pumba → list pumba jobs
// GET  /api/chaos?type=region → region health
// GET  /api/chaos?type=lambda-failure → lambda failures
// GET  /api/chaos?type=containers → kumostack containers
export async function GET(req: Request) {
  const t = new URL(req.url).searchParams.get("type");
  try {
    if (t === "pumba")          return proxy(`${BASE}/pumba-jobs`);
    if (t === "region")         return proxy(`${BASE}/region`);
    if (t === "lambda-failure") return proxy(`${BASE}/lambda-failure`);
    if (t === "containers")     return proxy(`${BASE}/containers`);
    return proxy(BASE);
  } catch { return Response.json({ rules: [] }); }
}

export async function POST(req: Request) {
  const t = new URL(req.url).searchParams.get("type");
  try {
    const body = await req.json();
    const endpoint =
      t === "pumba"          ? `${BASE}/pumba` :
      t === "region"         ? `${BASE}/region` :
      t === "lambda-failure" ? `${BASE}/lambda-failure` :
      BASE;
    return proxy(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) { return Response.json({ error: String(e) }, { status: 500 }); }
}

export async function DELETE(req: Request) {
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  const t  = url.searchParams.get("type");
  try {
    const endpoint =
      t === "region"         ? `${BASE}/region` :
      t === "lambda-failure" ? `${BASE}/lambda-failure${id ? `/${id}` : ""}` :
      id ? `${BASE}/${id}` : BASE;
    return proxy(endpoint, { method: "DELETE" });
  } catch (e) { return Response.json({ error: String(e) }, { status: 500 }); }
}

export async function PATCH(req: Request) {
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  if (!id) return Response.json({ error: "id required" }, { status: 400 });
  try {
    return proxy(`${BASE}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await req.json()),
    });
  } catch (e) { return Response.json({ error: String(e) }, { status: 500 }); }
}
