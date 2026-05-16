import { NextResponse } from "next/server";

const MINISTACK = process.env.KUMOSTACK_ENDPOINT ?? "http://localhost:4566";
const CREDS = {
  headers: {
    "X-Amz-Security-Token": "test",
    "Authorization":
      "AWS4-HMAC-SHA256 Credential=test/20240101/us-east-1/service/aws4_request, SignedHeaders=host, Signature=test",
  },
};

async function awsXml(service: string, path: string, action: string) {
  try {
    const url = `${MINISTACK}${path}?Action=${action}&Version=2012-11-05`;
    const res = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    const text = await res.text();
    return text;
  } catch {
    return "";
  }
}

async function awsJson(path: string, body: string, target: string) {
  try {
    const res = await fetch(`${MINISTACK}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-amz-json-1.0", "X-Amz-Target": target },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return await res.json();
  } catch {
    return null;
  }
}

function countXmlItems(xml: string, tag: string): number {
  const matches = xml.match(new RegExp(`<${tag}[^>]*>`, "g"));
  return matches ? matches.length : 0;
}

export async function GET() {
  const [
    s3Xml, sqsXml, snsXml, lambdaJson, ddbJson,
    sfnJson, logsJson, secretsJson, cfJson,
    kinesisJson, ecsJson, eksJson,
  ] = await Promise.allSettled([
    awsXml("s3", "/", "ListAllMyBuckets"),
    awsXml("sqs", "/", "ListQueues"),
    awsXml("sns", "/", "ListTopics"),
    fetch(`${MINISTACK}/2015-03-31/functions/`, { cache: "no-store", signal: AbortSignal.timeout(3000) }).then((r) => r.json()).catch(() => null),
    awsJson("/", JSON.stringify({}), "DynamoDB_20120810.ListTables"),
    awsJson("/", JSON.stringify({ maxResults: 100 }), "AmazonStatesService.ListStateMachines"),
    awsJson("/", JSON.stringify({ limit: 50 }), "Logs_20140328.DescribeLogGroups"),
    fetch(`${MINISTACK}/secretsmanager/`, { method: "POST", headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "secretsmanager.ListSecrets" }, body: "{}", cache: "no-store", signal: AbortSignal.timeout(3000) }).then((r) => r.json()).catch(() => null),
    awsXml("cloudformation", "/", "ListStacks"),
    awsJson("/", JSON.stringify({}), "Kinesis_20131202.ListStreams"),
    fetch(`${MINISTACK}/?Action=ListClusters`, { cache: "no-store", signal: AbortSignal.timeout(3000) }).then((r) => r.text()).catch(() => ""),
    fetch(`${MINISTACK}/clusters`, { headers: { "Accept": "application/json" }, cache: "no-store", signal: AbortSignal.timeout(3000) }).then((r) => r.json()).catch(() => null),
  ]);

  const val = <T>(r: PromiseSettledResult<T>, fallback: T) =>
    r.status === "fulfilled" ? r.value : fallback;

  const s3    = countXmlItems(val(s3Xml, ""), "Name");
  const sqs   = countXmlItems(val(sqsXml, ""), "QueueUrl");
  const sns   = countXmlItems(val(snsXml, ""), "TopicArn");
  const lData = val(lambdaJson, null) as { Functions?: unknown[] } | null;
  const lambda = lData?.Functions?.length ?? 0;
  const dData = val(ddbJson, null) as { TableNames?: string[] } | null;
  const dynamodb = dData?.TableNames?.length ?? 0;
  const sfData = val(sfnJson, null) as { stateMachines?: unknown[] } | null;
  const stepfunctions = sfData?.stateMachines?.length ?? 0;
  const lgData = val(logsJson, null) as { logGroups?: unknown[] } | null;
  const logs = lgData?.logGroups?.length ?? 0;
  const secData = val(secretsJson, null) as { SecretList?: unknown[] } | null;
  const secrets = secData?.SecretList?.length ?? 0;
  const stacks = countXmlItems(val(cfJson, ""), "StackName");
  const kData = val(kinesisJson, null) as { StreamNames?: string[] } | null;
  const kinesis = kData?.StreamNames?.length ?? 0;

  const counts: Record<string, number> = {
    s3, sqs, sns, lambda, dynamodb, stepfunctions, logs, secretsmanager: secrets,
    cloudformation: stacks, kinesis,
  };

  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return NextResponse.json({ counts, total });
}
