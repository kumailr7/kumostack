import { NextRequest, NextResponse } from "next/server";
import { S3Client, ListBucketsCommand } from "@aws-sdk/client-s3";

const ENDPOINT = process.env.KUMOSTACK_ENDPOINT || "http://localhost:4566";

export async function GET(req: NextRequest) {
  const region = req.nextUrl.searchParams.get("region") ?? "us-east-1";
  const start = Date.now();
  try {
    const client = new S3Client({
      endpoint: ENDPOINT,
      region,
      forcePathStyle: true,
      credentials: { accessKeyId: process.env.AWS_ACCESS_KEY_ID || "test", secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || "test" },
      requestHandler: { requestTimeout: 6000 },
    });
    await client.send(new ListBucketsCommand({}));
    return NextResponse.json({ region, status: 200, ok: true, latency_ms: Date.now() - start, service: "S3:ListBuckets" });
  } catch (e: unknown) {
    const err = e as { $metadata?: { httpStatusCode?: number }; message?: string; name?: string };
    const httpStatus = err.$metadata?.httpStatusCode ?? 503;
    return NextResponse.json({
      region,
      status: httpStatus,
      ok: false,
      error: err.message ?? err.name ?? "Unknown error",
      latency_ms: Date.now() - start,
      service: "S3:ListBuckets",
    });
  }
}
