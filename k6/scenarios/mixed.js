/**
 * K6 — Mixed AWS Load Test
 * Hammers S3, SQS, and DynamoDB simultaneously with weighted scenarios.
 * Best used to simulate realistic multi-service workloads.
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import { awsHeaders, ENDPOINT } from "../lib/aws.js";

const VUS      = parseInt(__ENV.K6_VUS      || "20");
const DURATION = __ENV.K6_DURATION          || "120s";

export const options = {
  scenarios: {
    s3_workload: {
      executor:    "constant-vus",
      vus:         Math.ceil(VUS * 0.4),
      duration:    DURATION,
      exec:        "s3Scenario",
    },
    sqs_workload: {
      executor:    "constant-vus",
      vus:         Math.ceil(VUS * 0.4),
      duration:    DURATION,
      exec:        "sqsScenario",
    },
    dynamo_workload: {
      executor:    "constant-vus",
      vus:         Math.ceil(VUS * 0.2),
      duration:    DURATION,
      exec:        "dynamoScenario",
    },
  },
  thresholds: {
    http_req_failed:   ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

const errCounter   = new Counter("kumo_mixed_errors");
const s3Dur        = new Trend("kumo_mixed_s3_duration",    true);
const sqsDur       = new Trend("kumo_mixed_sqs_duration",   true);
const dynamoDur    = new Trend("kumo_mixed_dynamo_duration", true);

const BUCKET   = "k6-mixed-bucket";
const QUEUE    = `${ENDPOINT}/000000000000/k6-mixed-queue`;
const DDB_URL  = ENDPOINT;
const DDB_TABLE = "k6-mixed-table";

export function setup() {
  // S3 bucket
  const bucketHdrs = awsHeaders("PUT", `${ENDPOINT}/${BUCKET}`, "s3", "");
  bucketHdrs["content-type"] = "application/xml";
  http.put(`${ENDPOINT}/${BUCKET}`, "", { headers: bucketHdrs });

  // SQS queue
  const sqsBody = "Action=CreateQueue&QueueName=k6-mixed-queue&Version=2012-11-05";
  const sqsHdrs = awsHeaders("POST", `${ENDPOINT}/`, "sqs", sqsBody);
  sqsHdrs["content-type"] = "application/x-www-form-urlencoded";
  http.post(`${ENDPOINT}/`, sqsBody, { headers: sqsHdrs });

  // DynamoDB table
  const ddbBody = JSON.stringify({
    TableName:            DDB_TABLE,
    KeySchema:            [{ AttributeName: "id", KeyType: "HASH" }],
    AttributeDefinitions: [{ AttributeName: "id", AttributeType: "S" }],
    BillingMode:          "PAY_PER_REQUEST",
  });
  const ddbHdrs = awsHeaders("POST", DDB_URL, "dynamodb", ddbBody, "DynamoDB_20120810.CreateTable");
  http.post(DDB_URL, ddbBody, { headers: ddbHdrs });
}

export function s3Scenario() {
  const key  = `mixed/${__VU}-${__ITER}.bin`;
  const body = `mixed-payload-${Date.now()}`;
  const url  = `${ENDPOINT}/${BUCKET}/${key}`;
  const hdrs = awsHeaders("PUT", url, "s3", body);
  hdrs["content-type"] = "text/plain";
  const res  = http.put(url, body, { headers: hdrs, tags: { name: "mixed_s3" } });
  s3Dur.add(res.timings.duration);
  if (!check(res, { "s3 ok": r => r.status === 200 })) errCounter.add(1);
  sleep(0.1);
}

export function sqsScenario() {
  const body = `Action=SendMessage&MessageBody=mixed-${__VU}-${__ITER}&Version=2012-11-05`;
  const hdrs = awsHeaders("POST", QUEUE, "sqs", body);
  hdrs["content-type"] = "application/x-www-form-urlencoded";
  const res  = http.post(QUEUE, body, { headers: hdrs, tags: { name: "mixed_sqs" } });
  sqsDur.add(res.timings.duration);
  if (!check(res, { "sqs ok": r => r.status === 200 })) errCounter.add(1);
  sleep(0.1);
}

export function dynamoScenario() {
  const putBody = JSON.stringify({
    TableName: DDB_TABLE,
    Item: { id: { S: `${__VU}-${__ITER}` }, ts: { N: String(Date.now()) } },
  });
  const hdrs = awsHeaders("POST", DDB_URL, "dynamodb", putBody, "DynamoDB_20120810.PutItem");
  const res  = http.post(DDB_URL, putBody, { headers: hdrs, tags: { name: "mixed_dynamo" } });
  dynamoDur.add(res.timings.duration);
  if (!check(res, { "dynamo ok": r => r.status === 200 })) errCounter.add(1);
  sleep(0.05);
}
