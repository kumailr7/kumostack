/**
 * K6 — SQS Load Test
 * Send then receive messages against a local SQS queue.
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
    http_req_duration: ["p(95)<1000"],
  },
};

const sendErrors   = new Counter("kumo_sqs_send_errors");
const receiveErrors = new Counter("kumo_sqs_receive_errors");
const sendDur      = new Trend("kumo_sqs_send_duration", true);
const receiveDur   = new Trend("kumo_sqs_receive_duration", true);

const QUEUE_NAME = "k6-load-queue";
const ACCOUNT_ID = "000000000000";

let QUEUE_URL;

export function setup() {
  // Create queue
  const createUrl  = `${ENDPOINT}/`;
  const createBody = `Action=CreateQueue&QueueName=${QUEUE_NAME}&Version=2012-11-05`;
  const hdrs       = awsHeaders("POST", createUrl, "sqs", createBody);
  hdrs["content-type"] = "application/x-www-form-urlencoded";
  http.post(createUrl, createBody, { headers: hdrs });

  return { queueUrl: `${ENDPOINT}/${ACCOUNT_ID}/${QUEUE_NAME}` };
}

export default function ({ queueUrl }) {
  const url = queueUrl || `${ENDPOINT}/${ACCOUNT_ID}/${QUEUE_NAME}`;

  // SendMessage
  const msgBody  = `K6 message VU=${__VU} ITER=${__ITER} ts=${Date.now()}`;
  const sendBody = `Action=SendMessage&MessageBody=${encodeURIComponent(msgBody)}&Version=2012-11-05`;
  const sendHdrs = awsHeaders("POST", url, "sqs", sendBody);
  sendHdrs["content-type"] = "application/x-www-form-urlencoded";
  const sendRes  = http.post(url, sendBody, { headers: sendHdrs, tags: { name: "sqs_send" } });
  sendDur.add(sendRes.timings.duration);
  if (!check(sendRes, { "Send 200": r => r.status === 200 })) sendErrors.add(1);

  // ReceiveMessage
  const recvBody = "Action=ReceiveMessage&MaxNumberOfMessages=1&Version=2012-11-05";
  const recvHdrs = awsHeaders("POST", url, "sqs", recvBody);
  recvHdrs["content-type"] = "application/x-www-form-urlencoded";
  const recvRes  = http.post(url, recvBody, { headers: recvHdrs, tags: { name: "sqs_recv" } });
  receiveDur.add(recvRes.timings.duration);
  if (!check(recvRes, { "Recv 200": r => r.status === 200 })) receiveErrors.add(1);

  sleep(0.1);
}
