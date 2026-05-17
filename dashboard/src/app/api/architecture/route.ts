import { NextResponse } from "next/server";
import { S3Client, ListBucketsCommand } from "@aws-sdk/client-s3";
import { EC2Client, DescribeInstancesCommand } from "@aws-sdk/client-ec2";
import {
  ElasticLoadBalancingV2Client,
  DescribeLoadBalancersCommand,
  DescribeTargetGroupsCommand,
  DescribeTargetHealthCommand,
} from "@aws-sdk/client-elastic-load-balancing-v2";
import { CloudFrontClient, ListDistributionsCommand } from "@aws-sdk/client-cloudfront";
import { RDSClient, DescribeDBInstancesCommand } from "@aws-sdk/client-rds";
import { LambdaClient, ListFunctionsCommand, ListEventSourceMappingsCommand, GetFunctionCommand } from "@aws-sdk/client-lambda";
import { DynamoDBClient, ListTablesCommand } from "@aws-sdk/client-dynamodb";
import { SQSClient, ListQueuesCommand } from "@aws-sdk/client-sqs";
import { SNSClient, ListTopicsCommand, ListSubscriptionsCommand } from "@aws-sdk/client-sns";
import { WAFV2Client, ListWebACLsCommand, ListResourcesForWebACLCommand } from "@aws-sdk/client-wafv2";
import { ECRClient, DescribeRepositoriesCommand } from "@aws-sdk/client-ecr";
import { SecretsManagerClient, ListSecretsCommand } from "@aws-sdk/client-secrets-manager";
import { EKSClient, ListClustersCommand, DescribeClusterCommand } from "@aws-sdk/client-eks";

const ENDPOINT = process.env.KUMOSTACK_ENDPOINT || "http://localhost:4566";
const REGION = process.env.AWS_REGION || "us-east-1";

const baseConfig = {
  endpoint: ENDPOINT,
  region: REGION,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || "test",
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || "test",
  },
};

export interface ArchNode {
  id: string;
  type: string;
  data: { label: string; service: string; status: string; meta: Record<string, string> };
  position: { x: number; y: number };
}

export interface ArchEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
  label?: string;
}

async function tryFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try { return await fn(); } catch { return null; }
}

const TIER_X: Record<string, number> = {
  internet:   80,
  security:   280,
  cdn:        480,
  networking: 680,
  registry:   860,
  compute:    1060,
  storage:    480,   // below CDN column
  database:   1280,
  messaging:  1480,
  secrets:    1280,  // below DATABASE column — renders in bottom row directly under RDS
};

export const TIER_LABELS_BY_X: Record<number, string> = {
  80:   "Internet",
  280:  "Security",
  480:  "CDN / Edge",
  680:  "Networking",
  860:  "Registry",
  1060: "Compute",
  1280: "Database",
  1480: "Messaging",
};

// Tiers that render below the main horizontal flow instead of inline with it
const BOTTOM_TIERS = new Set(["storage", "secrets"]);

function layoutNodes(groups: Record<string, ArchNode[]>): ArchNode[] {
  const GAP      = 240;
  const MAIN_Y   = 380;   // vertical centre of main flow
  const BOTTOM_Y = 720;   // vertical centre of bottom row (storage / origins)

  // Split into main-row and bottom-row buckets keyed by x
  const byX = new Map<number, { main: ArchNode[]; bottom: ArchNode[] }>();
  for (const [tier, nodes] of Object.entries(groups)) {
    const x = TIER_X[tier] ?? 100;
    if (!byX.has(x)) byX.set(x, { main: [], bottom: [] });
    const bucket = BOTTOM_TIERS.has(tier) ? "bottom" : "main";
    byX.get(x)![bucket].push(...nodes);
  }

  const result: ArchNode[] = [];
  for (const [x, { main, bottom }] of byX.entries()) {
    main.forEach((n, i) => {
      result.push({ ...n, position: { x, y: MAIN_Y + (i - (main.length - 1) / 2) * GAP } });
    });
    bottom.forEach((n, i) => {
      result.push({ ...n, position: { x, y: BOTTOM_Y + i * GAP } });
    });
  }
  return result;
}

function node(id: string, label: string, service: string, status: string, meta: Record<string, string> = {}): ArchNode {
  return { id, type: "awsNode", data: { label, service, status, meta: { region: REGION, ...meta } }, position: { x: 0, y: 0 } };
}

function edge(source: string, target: string, label?: string): ArchEdge {
  return { id: `${source}--${target}`, source, target, animated: true, label };
}

export async function GET() {
  const edges: ArchEdge[] = [];
  const groups: Record<string, ArchNode[]> = {
    internet: [], security: [], cdn: [], networking: [], registry: [],
    compute: [], storage: [], database: [], messaging: [], secrets: [],
  };
  const snsArnToNodeId = new Map<string, string>();

  // Internet entry node — always present as the user/traffic source
  groups.internet.push(node("internet", "Internet", "internet", "active"));

  // Internal KumoStack buckets that belong to the observability stack, not user workloads
  const INFRA_BUCKETS = new Set(["ministack-logs", "kumostack-logs", "logs-cold-archive", "logs-rds-archive"]);

  // S3 — skip infra/observability buckets so they don't clutter the diagram
  const s3 = new S3Client({ ...baseConfig, forcePathStyle: true });
  for (const b of (await tryFetch(() => s3.send(new ListBucketsCommand({}))))?.Buckets ?? []) {
    const name = b.Name ?? "bucket";
    if (INFRA_BUCKETS.has(name)) continue;
    groups.storage.push(node(`s3-${name}`, name, "s3", "available"));
  }

  // CloudFront
  // - ListDistributions: returns summaries (no Origins in KumoStack's response)
  // - GetDistribution:   returns XML with ns0: namespace prefix that confuses SDK
  // Workaround: raw-fetch the distribution XML and extract DomainName with regex
  const cf = new CloudFrontClient(baseConfig);
  const cfSummaries = (await tryFetch(() => cf.send(new ListDistributionsCommand({}))))?.DistributionList?.Items ?? [];

  for (const summary of cfSummaries) {
    if (!summary.Id) continue;
    const cfId   = `cf-${summary.Id}`;
    const domain = summary.DomainName ?? "";
    const label  = (summary.Aliases?.Items?.[0] || domain || summary.Id).slice(0, 28);

    groups.cdn.push(node(cfId, label, "cloudfront", summary.Status ?? "Deployed", {
      domain, id: summary.Id,
    }));

    // Raw-fetch the distribution XML — KumoStack stores config with ns0: prefix
    // that the AWS SDK fails to deserialise correctly, so we parse it ourselves
    try {
      const xml = await fetch(
        `${ENDPOINT}/2020-05-31/distribution/${summary.Id}`,
        { headers: { Authorization: "AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/cloudfront/aws4_request" } }
      ).then((r) => r.text());

      // Pull every DomainName that looks like an S3 origin
      const originMatches = xml.matchAll(/<[^>]*DomainName[^>]*>([^<]+\.s3[^<]*amazonaws\.com)<\/[^>]*DomainName>/g);
      for (const m of originMatches) {
        const rawDomain = m[1];
        const s3Name = rawDomain
          .replace(/\.s3\.[a-z0-9-]+\.amazonaws\.com$/, "")
          .replace(/\.s3\.amazonaws\.com$/, "");
        if (s3Name && groups.storage.some((n) => n.id === `s3-${s3Name}`)) {
          edges.push(edge(cfId, `s3-${s3Name}`, "origin"));
        }
      }
    } catch { /* ignore — edge is optional */ }
  }
  // keep cfDists alias for ALB matching below
  const cfDists = cfSummaries;

  // ECR — separate registry tier so it doesn't crowd Compute
  const ecr = new ECRClient(baseConfig);
  for (const repo of (await tryFetch(() => ecr.send(new DescribeRepositoriesCommand({}))))?.repositories ?? []) {
    const name = repo.repositoryName ?? "repo";
    groups.registry.push(node(`ecr-${name}`, name, "ecr", "active", { uri: repo.repositoryUri ?? "" }));
  }

  // EC2
  const ec2 = new EC2Client(baseConfig);
  const reservations = (await tryFetch(() => ec2.send(new DescribeInstancesCommand({}))))?.Reservations ?? [];
  for (const r of reservations) {
    for (const inst of r.Instances ?? []) {
      const id = inst.InstanceId ?? "?";
      const tags = Object.fromEntries((inst.Tags ?? []).map((t) => [t.Key ?? "", t.Value ?? ""]));
      const name = tags["Name"] ?? id;
      const nid = `ec2-${id}`;
      groups.compute.push(node(nid, name, "ec2", inst.State?.Name ?? "unknown", {
        instanceType: inst.InstanceType ?? "", instanceId: id,
        rds: tags["rds"] ?? "", ecr: tags["ecr"] ?? "",
      }));
      if (tags["rds"])  edges.push(edge(nid, `rds-${tags["rds"]}`));
      if (tags["ecr"])  edges.push(edge(`ecr-${tags["ecr"]}`, nid, "pull"));
    }
  }

  // ALB
  const alb = new ElasticLoadBalancingV2Client(baseConfig);
  const lbs = (await tryFetch(() => alb.send(new DescribeLoadBalancersCommand({}))))?.LoadBalancers ?? [];
  for (const lb of lbs) {
    const lbName = lb.LoadBalancerName ?? "alb";
    const lbId = `alb-${lbName}`;
    const lbArn = lb.LoadBalancerArn ?? "";
    groups.networking.push(node(lbId, lbName, "alb", lb.State?.Code ?? "active", {
      dns: lb.DNSName ?? "", arn: lbArn,
    }));
    // CloudFront → ALB
    for (const dist of cfDists) {
      for (const origin of dist.Origins?.Items ?? []) {
        if (lb.DNSName && (origin.DomainName ?? "").includes(lb.DNSName))
          edges.push(edge(`cf-${dist.Id}`, lbId, "origin"));
      }
    }
    // ALB → EC2 via target groups
    if (lbArn) {
      const tgs = (await tryFetch(() => alb.send(new DescribeTargetGroupsCommand({ LoadBalancerArn: lbArn }))))?.TargetGroups ?? [];
      for (const tg of tgs) {
        if (!tg.TargetGroupArn) continue;
        const healths = (await tryFetch(() => alb.send(new DescribeTargetHealthCommand({ TargetGroupArn: tg.TargetGroupArn }))))?.TargetHealthDescriptions ?? [];
        for (const h of healths) {
          const tid = h.Target?.Id ?? "";
          if (!tid) continue;
          const ec2Id = `ec2-${tid}`;
          if (!groups.compute.some((n) => n.id === ec2Id))
            groups.compute.push(node(ec2Id, tid, "ec2", h.TargetHealth?.State ?? "unknown", { instanceId: tid }));
          edges.push(edge(lbId, ec2Id));
        }
      }
    }
  }

  // WAF
  const waf = new WAFV2Client(baseConfig);
  const acls = (await tryFetch(() => waf.send(new ListWebACLsCommand({ Scope: "REGIONAL" }))))?.WebACLs ?? [];
  for (const acl of acls) {
    const name = acl.Name ?? "waf";
    const arn = acl.ARN ?? "";
    const wafId = `waf-${name}`;
    groups.security.push(node(wafId, name, "wafv2", "active", { arn }));
    if (arn) {
      const assoc = (await tryFetch(() => waf.send(new ListResourcesForWebACLCommand({
        WebACLArn: arn, ResourceType: "APPLICATION_LOAD_BALANCER",
      }))))?.ResourceArns ?? [];
      for (const rArn of assoc) {
        const match = groups.networking.find((n) => n.data.meta?.arn === rArn);
        if (match) edges.push(edge(wafId, match.id, "protects"));
      }
    }
  }

  // RDS
  const rds = new RDSClient(baseConfig);
  for (const db of (await tryFetch(() => rds.send(new DescribeDBInstancesCommand({}))))?.DBInstances ?? []) {
    const dbId = db.DBInstanceIdentifier ?? "rds";
    groups.database.push(node(`rds-${dbId}`, dbId, "rds", db.DBInstanceStatus ?? "available", {
      engine: db.Engine ?? "", class: db.DBInstanceClass ?? "",
    }));
  }

  // DynamoDB
  const dynamo = new DynamoDBClient(baseConfig);
  for (const table of (await tryFetch(() => dynamo.send(new ListTablesCommand({}))))?.TableNames ?? [])
    groups.database.push(node(`dynamo-${table}`, table, "dynamodb", "active"));

  // SNS — populate snsArnToNodeId before Lambda so Lambda→SNS edges resolve
  const snsc = new SNSClient(baseConfig);
  const snsTopics = (await tryFetch(() => snsc.send(new ListTopicsCommand({}))))?.Topics ?? [];
  for (const t of snsTopics) {
    const arn = t.TopicArn ?? "";
    const name = arn.split(":").pop() ?? arn;
    const nid = `sns-${name}`;
    groups.messaging.push(node(nid, name, "sns", "active", { arn }));
    snsArnToNodeId.set(arn, nid);
  }

  // SQS — populate sqsArnToNodeId before ESM edges
  const sqsArnToNodeId = new Map<string, string>();
  const sqs = new SQSClient(baseConfig);
  const sqsUrls = (await tryFetch(() => sqs.send(new ListQueuesCommand({}))))?.QueueUrls ?? [];
  for (const url of sqsUrls) {
    const name = url.split("/").pop() ?? "queue";
    const sqsArn = `arn:aws:sqs:${REGION}:000000000000:${name}`;
    const nid = `sqs-${name}`;
    groups.messaging.push(node(nid, name, "sqs", "active", { url }));
    sqsArnToNodeId.set(sqsArn, nid);
  }

  // SNS → SQS subscription edges
  const subs = (await tryFetch(() => snsc.send(new ListSubscriptionsCommand({}))))?.Subscriptions ?? [];
  for (const sub of subs) {
    if (sub.Protocol !== "sqs") continue;
    const snsSrc = snsArnToNodeId.get(sub.TopicArn ?? "");
    const sqsDst = sqsArnToNodeId.get(sub.Endpoint ?? "");
    if (snsSrc && sqsDst) edges.push(edge(snsSrc, sqsDst, "publish"));
  }

  // Lambda — built after SNS/SQS so env-var edges resolve
  const lambda = new LambdaClient(baseConfig);
  const lambdaFns = (await tryFetch(() => lambda.send(new ListFunctionsCommand({}))))?.Functions ?? [];
  for (const fn of lambdaFns) {
    const name = fn.FunctionName ?? "fn";
    const nid = `lambda-${name}`;
    const envVars = fn.Environment?.Variables ?? {};
    groups.compute.push(node(nid, name, "lambda", "active", { runtime: fn.Runtime ?? "" }));
    for (const [k, v] of Object.entries(envVars)) {
      if ((k === "TABLE_NAME" || k.endsWith("_TABLE")) && v) {
        const dynId = `dynamo-${v}`;
        if (groups.database.some(n => n.id === dynId)) edges.push(edge(nid, dynId, "read/write"));
      }
      if ((k.includes("TOPIC") || k.includes("SNS")) && v.startsWith("arn:aws:sns")) {
        const snsDst = snsArnToNodeId.get(v);
        if (snsDst) edges.push(edge(nid, snsDst, "publish"));
      }
      if (k.includes("QUEUE") && v) {
        const queueName = v.split("/").pop() ?? "";
        const sqsDst = `sqs-${queueName}`;
        if (groups.messaging.some(n => n.id === sqsDst)) edges.push(edge(nid, sqsDst, "send"));
      }
    }
  }

  // SQS → Lambda (event source mappings)
  const esms = (await tryFetch(() => lambda.send(new ListEventSourceMappingsCommand({}))))?.EventSourceMappings ?? [];
  for (const esm of esms) {
    const src = esm.EventSourceArn ?? "";
    const fnName = esm.FunctionArn?.split(":").pop() ?? "";
    const srcId = sqsArnToNodeId.get(src) ?? snsArnToNodeId.get(src);
    const dstId = `lambda-${fnName}`;
    if (srcId && groups.compute.some(n => n.id === dstId))
      edges.push(edge(srcId, dstId, "trigger"));
  }

  // EKS
  const eks = new EKSClient(baseConfig);
  const clusterNames = (await tryFetch(() => eks.send(new ListClustersCommand({}))))?.clusters ?? [];
  for (const clusterName of clusterNames) {
    const cluster = (await tryFetch(() => eks.send(new DescribeClusterCommand({ name: clusterName }))))?.cluster;
    const status = cluster?.status ?? "ACTIVE";
    const eksId = `eks-${clusterName}`;
    groups.compute.push(node(eksId, clusterName, "eks", status.toLowerCase(), {
      endpoint: cluster?.endpoint ?? "", version: cluster?.version ?? "",
    }));
    // ALB → EKS: load balancer forwards traffic into the cluster
    for (const albNode of groups.networking.filter((n) => n.data.service === "alb")) {
      edges.push(edge(albNode.id, eksId, "forwards"));
    }
    // EKS → RDS: direct connection (resolved after RDS block)
    for (const rdsNode of groups.database.filter((n) => n.data.service === "rds")) {
      edges.push(edge(eksId, rdsNode.id, "connects"));
    }
  }

  // Secrets Manager
  const sm = new SecretsManagerClient(baseConfig);
  const secrets = (await tryFetch(() => sm.send(new ListSecretsCommand({}))))?.SecretList ?? [];
  for (const secret of secrets) {
    const name = secret.Name ?? "secret";
    const smId = `sm-${name}`;
    groups.secrets.push(node(smId, name, "secretsmanager", "active", { arn: secret.ARN ?? "" }));
    // RDS → Secrets Manager: match by exact id OR by rds/<base-name>/… convention
    // e.g. secret "rds/myapp/credentials" matches RDS instance "myapp-postgres"
    for (const rdsNode of groups.database.filter((n) => n.data.service === "rds")) {
      const dbId   = rdsNode.data.label;                       // "myapp-postgres"
      const dbBase = dbId.replace(/-?(postgres|mysql|aurora|mariadb)$/i, ""); // "myapp"
      const isMatch =
        name.includes(dbId) ||
        (name.startsWith("rds/") && (name.includes(dbBase) || dbBase.length <= 3)) ||
        name.includes(dbBase);
      if (isMatch) edges.push(edge(rdsNode.id, smId, "credentials"));
    }
    // EKS → Secrets Manager: cluster reads any rds/db credential secret
    if (name.includes("rds") || name.includes("db") || name.includes("credentials")) {
      for (const eksNode of groups.compute.filter((n) => n.data.service === "eks")) {
        edges.push(edge(eksNode.id, smId, "reads"));
      }
    }
  }

  // Internet entry wiring — connect to the leftmost service tier
  const cdnNodes  = groups.cdn.filter((n) => n.data.service === "cloudfront");
  const albNodes  = groups.networking.filter((n) => n.data.service === "alb");
  const wafNodes  = groups.security.filter((n) => n.data.service === "wafv2");
  if (cdnNodes.length > 0) {
    for (const cdn of cdnNodes) {
      edges.push(edge("internet", cdn.id));
      // CloudFront → ALB (dynamic /api/* origin)
      for (const alb of albNodes) edges.push(edge(cdn.id, alb.id, "origin"));
    }
    // WAF protects CDN
    for (const waf of wafNodes) {
      for (const cdn of cdnNodes) edges.push(edge(waf.id, cdn.id, "protects"));
    }
  } else if (albNodes.length > 0) {
    for (const alb of albNodes) edges.push(edge("internet", alb.id));
    for (const waf of wafNodes) {
      for (const alb of albNodes) edges.push(edge(waf.id, alb.id, "protects"));
    }
  } else {
    // No CDN/ALB — connect internet to first compute node
    for (const n of groups.compute.slice(0, 1)) edges.push(edge("internet", n.id));
  }

  // Layout + dedup edges
  const filled = Object.fromEntries(Object.entries(groups).filter(([, v]) => v.length > 0));
  const nodes = layoutNodes(filled);
  const seen = new Set<string>();
  const nodeIds = new Set(nodes.map((n) => n.id));
  const uniqueEdges = edges.filter((e) => {
    const key = `${e.source}→${e.target}`;
    if (seen.has(key) || !nodeIds.has(e.source) || !nodeIds.has(e.target)) return false;
    seen.add(key);
    return true;
  });

  return NextResponse.json({ nodes, edges: uniqueEdges, tierLabels: TIER_LABELS_BY_X });
}
