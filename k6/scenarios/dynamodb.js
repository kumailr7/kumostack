/**
 * K6 — DynamoDB Load Test
 * PutItem / GetItem on a local DynamoDB table.
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import { awsHeaders, ENDPOINT } from "../lib/aws.js";

const VUS      = parseInt(__ENV.K6_VUS      || "10");
const DURATION = __ENV.K6_DURATION          || "60s";

export const options = {
  vus:      VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed:   ["rate<0.05"],
    http_req_duration: ["p(95)<500"],
  },
};

const putErrors = new Counter("kumo_dynamo_put_errors");
const getErrors = new Counter("kumo_dynamo_get_errors");
const putDur    = new Trend("kumo_dynamo_put_duration", true);
const getDur    = new Trend("kumo_dynamo_get_duration", true);

const TABLE = "k6-load-table";
const URL   = ENDPOINT;

export function setup() {
  const createBody = JSON.stringify({
    TableName:            TABLE,
    KeySchema:            [{ AttributeName: "id", KeyType: "HASH" }],
    AttributeDefinitions: [{ AttributeName: "id", AttributeType: "S" }],
    BillingMode:          "PAY_PER_REQUEST",
  });
  const hdrs = awsHeaders("POST", URL, "dynamodb", createBody, "DynamoDB_20120810.CreateTable");
  http.post(URL, createBody, { headers: hdrs });
}

export default function () {
  const itemId = `vu${__VU}-iter${__ITER}`;

  // PutItem
  const putBody = JSON.stringify({
    TableName: TABLE,
    Item: {
      id:        { S: itemId },
      vu:        { N: String(__VU) },
      iteration: { N: String(__ITER) },
      ts:        { N: String(Date.now()) },
      payload:   { S: `load test payload from VU ${__VU}` },
    },
  });
  const putHdrs = awsHeaders("POST", URL, "dynamodb", putBody, "DynamoDB_20120810.PutItem");
  const putRes  = http.post(URL, putBody, { headers: putHdrs, tags: { name: "dynamo_put" } });
  putDur.add(putRes.timings.duration);
  if (!check(putRes, { "PutItem 200": r => r.status === 200 })) putErrors.add(1);

  // GetItem
  const getBody = JSON.stringify({
    TableName: TABLE,
    Key: { id: { S: itemId } },
  });
  const getHdrs = awsHeaders("POST", URL, "dynamodb", getBody, "DynamoDB_20120810.GetItem");
  const getRes  = http.post(URL, getBody, { headers: getHdrs, tags: { name: "dynamo_get" } });
  getDur.add(getRes.timings.duration);
  if (!check(getRes, { "GetItem 200": r => r.status === 200 })) getErrors.add(1);

  sleep(0.05);
}
