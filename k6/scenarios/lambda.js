/**
 * K6 — Lambda Load Test
 * Invoke a Lambda function repeatedly to measure cold start + invocation latency.
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend, Rate } from "k6/metrics";
import { awsHeaders, ENDPOINT } from "../lib/aws.js";

const VUS          = parseInt(__ENV.K6_VUS      || "5");
const DURATION     = __ENV.K6_DURATION          || "60s";
const FUNC_NAME    = __ENV.K6_LAMBDA_FUNCTION   || "k6-test-fn";

export const options = {
  vus:      VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed:       ["rate<0.10"],
    http_req_duration:     ["p(95)<5000"],
    kumo_lambda_errors:    ["count<5"],
  },
};

const invokeErrors = new Counter("kumo_lambda_errors");
const invokeDur    = new Trend("kumo_lambda_invoke_duration", true);
const successRate  = new Rate("kumo_lambda_success_rate");

export function setup() {
  // Create a minimal Lambda function (zip with inline Python handler)
  // KumoStack accepts a pre-built base64 zip; we use a placeholder
  const createBody = JSON.stringify({
    FunctionName: FUNC_NAME,
    Runtime:      "python3.11",
    Role:         "arn:aws:iam::000000000000:role/k6-role",
    Handler:      "index.handler",
    Code: {
      // Minimal valid Lambda zip (Python handler echoing the event)
      ZipFile: "UEsDBAoAAAAAAIdUZ1gAAAAAAAAAAAAAAAAGAAAAaW5kZXgucHkKZGVmIGhhbmRsZXIoZXZlbnQsIGNvbnRleHQpOgogICAgcmV0dXJuIHsiYm9keSI6ICJvayIsICJzdGF0dXNDb2RlIjogMjAwfQpQSwECHgMKAAAAAACHVGdYAAAAAAAAAAAAAAAABgAAAAAAAAAAABAAAAAAAAAAaW5kZXgucHlQSwUGAAAAAAEAAQA0AAAAJAAAAAAA",
    },
    Description: "K6 load test function",
  });
  const url  = `${ENDPOINT}/2015-03-31/functions`;
  const hdrs = awsHeaders("POST", url, "lambda", createBody);
  hdrs["content-type"] = "application/json";
  http.post(url, createBody, { headers: hdrs });
}

export default function () {
  const url      = `${ENDPOINT}/2015-03-31/functions/${FUNC_NAME}/invocations`;
  const payload  = JSON.stringify({ vu: __VU, iter: __ITER, ts: Date.now() });
  const hdrs     = awsHeaders("POST", url, "lambda", payload);
  hdrs["content-type"]          = "application/json";
  hdrs["x-amz-invocation-type"] = "RequestResponse";

  const res = http.post(url, payload, { headers: hdrs, tags: { name: "lambda_invoke" } });
  invokeDur.add(res.timings.duration);

  const ok = check(res, { "Invoke 200": r => r.status === 200 });
  successRate.add(ok);
  if (!ok) invokeErrors.add(1);

  sleep(0.2);
}
