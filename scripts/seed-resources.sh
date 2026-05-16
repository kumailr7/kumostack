#!/usr/bin/env bash
# Creates a realistic AWS architecture in KumoStack for testing the Architecture diagram.
#
# Topology:
#   WAF ──────────────────► ALB ──► EC2 ──► RDS ──► Secrets Manager
#   CloudFront ──────────► S3       ▲
#   ECR ─────────────────────────────┘
#
# Usage:
#   ./scripts/seed-resources.sh                   # targets localhost:4566
#   MINISTACK_ENDPOINT=http://... ./scripts/seed-resources.sh

set -euo pipefail

EP="${MINISTACK_ENDPOINT:-http://localhost:4566}"
REGION="us-east-1"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=$REGION
export AWS_PAGER=""

alias aws="aws --endpoint-url $EP"

ok()  { echo "  ✓ $*"; }
hdr() { echo; echo "── $* ──────────────────────────────"; }

# ── S3 ────────────────────────────────────────────────────────────────────────
hdr "S3"
aws s3api create-bucket --bucket my-app-static --endpoint-url $EP
ok "Bucket: my-app-static"

# ── CloudFront → S3 ───────────────────────────────────────────────────────────
hdr "CloudFront"
CF_ID=$(aws cloudfront create-distribution \
  --endpoint-url $EP \
  --distribution-config '{
    "CallerReference": "seed-cf-1",
    "Origins": {
      "Quantity": 1,
      "Items": [{
        "Id": "S3-my-app-static",
        "DomainName": "my-app-static.s3.amazonaws.com",
        "S3OriginConfig": {"OriginAccessIdentity": ""}
      }]
    },
    "DefaultCacheBehavior": {
      "TargetOriginId": "S3-my-app-static",
      "ViewerProtocolPolicy": "redirect-to-https",
      "ForwardedValues": {"QueryString": false, "Cookies": {"Forward": "none"}},
      "MinTTL": 0,
      "TrustedSigners": {"Enabled": false, "Quantity": 0}
    },
    "Comment": "My App CDN",
    "Enabled": true
  }' \
  --query 'Distribution.Id' --output text)
ok "Distribution: $CF_ID → origin: my-app-static.s3.amazonaws.com"

# ── ECR ───────────────────────────────────────────────────────────────────────
hdr "ECR"
ECR_URI=$(aws ecr create-repository \
  --repository-name my-app \
  --endpoint-url $EP \
  --query 'repository.repositoryUri' --output text)
ok "Repository: my-app  ($ECR_URI)"

# ── Secrets Manager (RDS credentials) ─────────────────────────────────────────
hdr "Secrets Manager"
SECRET_ARN=$(aws secretsmanager create-secret \
  --name "rds/my-app-db/credentials" \
  --description "RDS credentials for my-app-db" \
  --secret-string '{"username":"admin","password":"MySecret123!"}' \
  --endpoint-url $EP \
  --query 'ARN' --output text)
ok "Secret: rds/my-app-db/credentials"

# ── RDS ───────────────────────────────────────────────────────────────────────
hdr "RDS"
aws rds create-db-instance \
  --db-instance-identifier my-app-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password "MySecret123!" \
  --allocated-storage 20 \
  --no-multi-az \
  --endpoint-url $EP > /dev/null
ok "DB instance: my-app-db (postgres)"

# ── VPC + subnets ─────────────────────────────────────────────────────────────
hdr "VPC / Subnets"
VPC_ID=$(aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --endpoint-url $EP \
  --query 'Vpcs[0].VpcId' --output text)

SUBNETS=$(aws ec2 describe-subnets \
  --filters Name=vpc-id,Values=$VPC_ID \
  --endpoint-url $EP \
  --query 'Subnets[*].SubnetId' --output text)
SUBNET1=$(echo $SUBNETS | awk '{print $1}')
SUBNET2=$(echo $SUBNETS | awk '{print $2}')
ok "VPC: $VPC_ID  Subnets: $SUBNET1  $SUBNET2"

# ── EC2 (tagged so diagram knows it connects to RDS and uses ECR) ─────────────
hdr "EC2"
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id ami-12345678 \
  --instance-type t3.micro \
  --count 1 \
  --subnet-id $SUBNET1 \
  --endpoint-url $EP \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=my-app-server},{Key=rds,Value=my-app-db},{Key=ecr,Value=my-app}]" \
  --query 'Instances[0].InstanceId' --output text)
ok "Instance: $INSTANCE_ID (my-app-server)"
ok "  tags → rds:my-app-db  ecr:my-app"

# ── ALB + target group + listener ────────────────────────────────────────────
hdr "ALB"
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name my-app-alb \
  --subnets $SUBNET1 $SUBNET2 \
  --type application \
  --endpoint-url $EP \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)
ok "ALB: my-app-alb"

TG_ARN=$(aws elbv2 create-target-group \
  --name my-app-tg \
  --protocol HTTP \
  --port 80 \
  --vpc-id $VPC_ID \
  --target-type instance \
  --endpoint-url $EP \
  --query 'TargetGroups[0].TargetGroupArn' --output text)
ok "Target group: my-app-tg"

aws elbv2 register-targets \
  --target-group-arn $TG_ARN \
  --targets Id=$INSTANCE_ID \
  --endpoint-url $EP
ok "Registered $INSTANCE_ID as target"

aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --endpoint-url $EP > /dev/null
ok "Listener: HTTP:80 → my-app-tg"

# ── WAF → ALB ─────────────────────────────────────────────────────────────────
hdr "WAF"
WAF_ARN=$(aws wafv2 create-web-acl \
  --name my-app-waf \
  --scope REGIONAL \
  --default-action '{"Allow":{}}' \
  --visibility-config 'SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=my-app-waf' \
  --rules '[]' \
  --endpoint-url $EP \
  --query 'Summary.ARN' --output text)
ok "WebACL: my-app-waf"

aws wafv2 associate-web-acl \
  --web-acl-arn $WAF_ARN \
  --resource-arn $ALB_ARN \
  --endpoint-url $EP
ok "Associated WAF → ALB: my-app-alb"

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════"
echo " All resources created successfully!"
echo "═══════════════════════════════════════════"
echo
echo " CloudFront ──► S3 (my-app-static)"
echo " WAF ──────────► ALB (my-app-alb)"
echo " ALB ──────────► EC2 ($INSTANCE_ID)"
echo " ECR ──────────► EC2 (via tag)"
echo " EC2 ──────────► RDS (my-app-db, via tag)"
echo " RDS ──────────► Secrets Manager (via name prefix)"
echo
echo " Open http://localhost:3003 → Architecture tab"
echo
