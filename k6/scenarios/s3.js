/**
 * K6 — S3 Load Test
 * PUT then GET objects across multiple buckets.
 * Metrics are pushed to Prometheus via remote-write.
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
    http_req_duration: ["p(95)<2000"],
  },
};

const putErrors = new Counter("kumo_s3_put_errors");
const getErrors = new Counter("kumo_s3_get_errors");
const putDur    = new Trend("kumo_s3_put_duration", true);
const getDur    = new Trend("kumo_s3_get_duration", true);

const BUCKET  = "k6-load-test";
const REGION  = __ENV.AWS_REGION || "us-east-1";

// Create bucket once in setup
export function setup() {
  const url  = `${ENDPOINT}/${BUCKET}`;
  const body = `<CreateBucketConfiguration><LocationConstraint>${REGION}</LocationConstraint></CreateBucketConfiguration>`;
  const hdrs = awsHeaders("PUT", url, "s3", body);
  hdrs["content-type"] = "application/xml";
  http.put(url, body, { headers: hdrs });
}

export default function () {
  const key  = `load-test/${__VU}-${__ITER}.txt`;
  const body = `K6 load test payload — VU ${__VU} iter ${__ITER} ts ${Date.now()}`;

  // PUT
  const putUrl  = `${ENDPOINT}/${BUCKET}/${key}`;
  const putHdrs = awsHeaders("PUT", putUrl, "s3", body);
  putHdrs["content-type"] = "text/plain";
  const putRes  = http.put(putUrl, body, { headers: putHdrs, tags: { name: "s3_put" } });
  putDur.add(putRes.timings.duration);
  if (!check(putRes, { "PUT 200": r => r.status === 200 })) putErrors.add(1);

  // GET
  const getHdrs = awsHeaders("GET", putUrl, "s3", "");
  getHdrs["content-type"] = "text/plain";
  const getRes  = http.get(putUrl, { headers: getHdrs, tags: { name: "s3_get" } });
  getDur.add(getRes.timings.duration);
  if (!check(getRes, { "GET 200": r => r.status === 200 })) getErrors.add(1);

  sleep(0.1);
}
