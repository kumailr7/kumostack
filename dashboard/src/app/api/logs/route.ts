import * as http from "http";

const CONTAINER = process.env.MINISTACK_CONTAINER ?? "kumostack";
const SOCKET    = "/var/run/docker.sock";
const TAIL      = 300;

/**
 * Docker log stream uses an 8-byte multiplexing header per entry:
 *   byte 0    : stream type  (1=stdout, 2=stderr)
 *   bytes 1-3 : padding (zeros)
 *   bytes 4-7 : uint32 big-endian payload length
 *   bytes 8…  : log text
 *
 * We strip the headers and return plain text.
 */
function parseDockerLogs(raw: Buffer): string {
  const lines: string[] = [];
  let offset = 0;

  while (offset + 8 <= raw.length) {
    const size = raw.readUInt32BE(offset + 4);
    const end  = offset + 8 + size;
    if (end > raw.length) break;

    const line = raw.slice(offset + 8, end).toString("utf8").trimEnd();
    if (line) lines.push(line);
    offset = end;
  }

  // Fallback: if we got no parsed lines, the daemon might have used
  // a non-multiplexed TTY stream — just return the raw text.
  return lines.length > 0
    ? lines.join("\n")
    : raw.toString("utf8");
}

function fetchDockerLogs(): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const path = `/containers/${encodeURIComponent(CONTAINER)}/logs?stdout=1&stderr=1&tail=${TAIL}&timestamps=1`;

    const req = http.request(
      { socketPath: SOCKET, path, method: "GET" },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c: Buffer) => chunks.push(c));
        res.on("end",  () => resolve(Buffer.concat(chunks)));
      }
    );

    req.setTimeout(5000, () => { req.destroy(); reject(new Error("timeout")); });
    req.on("error", reject);
    req.end();
  });
}

export async function GET() {
  try {
    const raw  = await fetchDockerLogs();
    const text = parseDockerLogs(raw);
    return new Response(text || "(no logs yet)", {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(
      `# Could not read Docker logs\n# ${msg}\n# Make sure /var/run/docker.sock is mounted in the dashboard container.`,
      { status: 200, headers: { "Content-Type": "text/plain" } }
    );
  }
}
