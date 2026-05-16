import { execFile } from "child_process";
import { promisify } from "util";

const run = promisify(execFile);

// Only these container names may be managed — prevents injection via spoofed requests.
const ALLOWED_CONTAINERS = new Set([
  "kumostack-mailhog",
  "kumostack-wiremock",
  "kumostack-stripe",
  "kumostack-httpbin",
  "kumostack-typedb",
  "kumostack-paradedb",
]);

function validate(name: string | null): name is string {
  return !!name && ALLOWED_CONTAINERS.has(name);
}

// GET /api/extensions/docker?name=kumostack-mailhog
// Returns { running: boolean, status: string }
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const name = searchParams.get("name");

  if (!validate(name)) {
    return Response.json({ error: "unknown container" }, { status: 400 });
  }

  try {
    const { stdout } = await run("docker", [
      "inspect", "--format", "{{.State.Status}}", name,
    ]);
    const state = stdout.trim();
    return Response.json({ running: state === "running", status: state });
  } catch {
    // container doesn't exist yet
    return Response.json({ running: false, status: "absent" });
  }
}

interface PortMapping { host: number; container: number }
interface LaunchBody {
  image: string;
  containerName: string;
  ports: PortMapping[];
  env?: Record<string, string>;
}

// POST /api/extensions/docker
// Body: { image, containerName, ports, env? }
export async function POST(req: Request) {
  let body: LaunchBody;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid body" }, { status: 400 });
  }

  const { image, containerName, ports, env } = body;

  if (!validate(containerName)) {
    return Response.json({ error: "unknown container" }, { status: 400 });
  }

  // Build args — no shell interpolation, all values go as discrete array elements
  const args: string[] = ["run", "-d", "--name", containerName, "--label", "kumostack-extension=true"];

  for (const p of ports) {
    args.push("-p", `${p.host}:${p.container}`);
  }

  for (const [k, v] of Object.entries(env ?? {})) {
    args.push("-e", `${k}=${v}`);
  }

  args.push(image);

  try {
    await run("docker", args);
    return Response.json({ ok: true });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);

    // Container already exists but stopped — remove it and retry
    if (msg.includes("already in use") || msg.includes("Conflict")) {
      try {
        await run("docker", ["rm", containerName]);
        await run("docker", args);
        return Response.json({ ok: true });
      } catch (e2: unknown) {
        return Response.json({ error: e2 instanceof Error ? e2.message : String(e2) }, { status: 500 });
      }
    }

    return Response.json({ error: msg }, { status: 500 });
  }
}

// DELETE /api/extensions/docker?name=kumostack-mailhog
export async function DELETE(req: Request) {
  const { searchParams } = new URL(req.url);
  const name = searchParams.get("name");

  if (!validate(name)) {
    return Response.json({ error: "unknown container" }, { status: 400 });
  }

  try {
    await run("docker", ["stop", name]);
    await run("docker", ["rm", name]);
    return Response.json({ ok: true });
  } catch (e: unknown) {
    return Response.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
