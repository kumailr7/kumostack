# AWS Organizations & Service Control Policies

KumoStack emulates AWS Organizations with **real Service Control Policies (SCPs)** that are
enforced at the API level — exactly like the real AWS control plane.

---

## Overview

| Feature | Support |
|---|---|
| Create / list / delete SCPs | ✅ Full API |
| Attach SCPs to accounts and OUs | ✅ Full API |
| Enable / disable SCPs from the dashboard | ✅ Toggle button |
| SCP enforcement on S3 `CreateBucket` | ✅ Returns AWS-format `AccessDenied` |
| SCP enforcement on S3 `DeleteBucket` | ✅ Returns AWS-format `AccessDenied` |
| SCP enforcement on EKS `DeleteCluster` | ✅ Returns AWS-format `AccessDenied` |
| Management-account gating | ✅ Only management account can manage SCPs |
| Cross-account AssumeRole log | ✅ Real-time log of every `sts:AssumeRole` call |

---

## Quick start

### 1. Create an SCP (management account only)

```bash
aws organizations create-policy \
  --name "DenyS3CreateInDev" \
  --description "Dev account: S3 bucket creation requires admin approval" \
  --type SERVICE_CONTROL_POLICY \
  --content '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "DenyBucketCreation",
      "Effect": "Deny",
      "Action": "s3:CreateBucket",
      "Resource": "*"
    }]
  }' \
  --endpoint-url http://localhost:4566
```

### 2. Attach to a dev account

```bash
aws organizations attach-policy \
  --policy-id p-xxxxxxxx \
  --target-id 111111111111 \
  --endpoint-url http://localhost:4566
```

### 3. Test enforcement

```bash
# This will be BLOCKED
aws s3 mb s3://my-test-bucket --endpoint-url http://localhost:4566

# Output:
# make_bucket failed: s3://my-test-bucket An error occurred (AccessDenied)
# when calling the CreateBucket operation:
# User: arn:aws:iam::000000000000:root is not authorized to perform: s3:CreateBucket
# on resource: arn:aws:s3:::my-test-bucket
# with an explicit deny in a service control policy.
# Contact your account administrator. Policy: 'DenyS3CreateInDev'
```

---

## Dashboard

The **Organizations** tab in the KumoStack dashboard provides a full management UI.

### Management Account requirement

Just like real AWS, **only the management account can create and manage SCPs**.

- Switch to the **management account** in the sidebar account switcher
- The SCP table becomes fully editable — toggle ENABLED/DISABLED per policy
- Member accounts (dev-team, staging, production, etc.) see a **read-only locked view**
  with a **"Switch to Management Account"** button

![SCP locked view — member account sees read-only policies with a switch prompt]

### SCP table columns

| Column | Description |
|---|---|
| Policy | Policy name (monospace) |
| Description | Human-readable purpose |
| Attached To | Account names / OU names (e.g. `dev-team, Engineering`) |
| Services | Auto-extracted from policy actions (e.g. `EKS, S3`) |
| Effect | `DENY` (red) or `ALLOW` (green) |
| Status | Toggle `ENABLED` / `DISABLED` — persists to KumoStack |

### Cross-Account Access Log

Every `sts:AssumeRole` call is recorded in real-time:

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::000000000000:role/AppDeployRole \
  --role-session-name ci-pipeline \
  --endpoint-url http://localhost:4566
```

The log shows: timestamp → source account → destination account → role name → session name → action.

---

## SCP enforcement details

KumoStack evaluates SCPs **before** routing to the service handler.

### Enforcement rules

1. **Conditional SCPs are skipped** — statements with `Condition` blocks (e.g. `aws:RequestedRegion`, `aws:PrincipalType`) are not evaluated since KumoStack does not resolve request context keys. This matches the "benefit of the doubt" principle.

2. **Account matching** — an SCP is evaluated if its `AttachedEntities` list contains the current account ID, or if the list is empty (treated as org-wide).

3. **First-match wins** — the evaluator returns on the first matching DENY statement.

### Currently enforced actions

| Service | Action | SCP evaluated |
|---|---|---|
| S3 | `s3:CreateBucket` | ✅ |
| S3 | `s3:DeleteBucket` | ✅ |
| EKS | `eks:DeleteCluster` | ✅ |
| EKS | `eks:UpdateClusterConfig` | ✅ |

### Error format (matches real AWS)

```
AccessDenied: User: arn:aws:iam::<account>:root is not authorized to perform:
<action> on resource: <arn> with an explicit deny in a service control policy.
Contact your account administrator. Policy: '<policy-name>'
```

---

## Example: EKS + S3 guardrails for dev account

This is the recommended baseline SCP for any dev account running EKS with an S3 frontend bucket.

```bash
aws organizations create-policy \
  --name "DevEKSAndS3Guardrails" \
  --description "Protect EKS cluster and S3 frontend bucket from accidental deletion" \
  --type SERVICE_CONTROL_POLICY \
  --content '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "DenyEKSClusterDeletion",
        "Effect": "Deny",
        "Action": ["eks:DeleteCluster", "eks:DeleteNodegroup"],
        "Resource": "*"
      },
      {
        "Sid": "DenyEKSS3BucketDeletion",
        "Effect": "Deny",
        "Action": ["s3:DeleteBucket", "s3:DeleteBucketPolicy"],
        "Resource": [
          "arn:aws:s3:::*-frontend",
          "arn:aws:s3:::*-cluster-*",
          "arn:aws:s3:::kumostack-*"
        ]
      },
      {
        "Sid": "DenyAccessToProdBuckets",
        "Effect": "Deny",
        "Action": "s3:*",
        "Resource": [
          "arn:aws:s3:::*-prod-*",
          "arn:aws:s3:::*-production-*"
        ]
      }
    ]
  }' \
  --endpoint-url http://localhost:4566
```

---

## Custom API endpoints

KumoStack exposes custom endpoints for the dashboard (also usable directly):

| Method | Path | Description |
|---|---|---|
| `GET` | `/_kumostack/organizations/scps` | List all SCPs with attachment and effect info |
| `POST` | `/_kumostack/organizations/scps` | Create an SCP |
| `PATCH` | `/_kumostack/organizations/scps/{id}` | Update `status` or `attachedTo` |
| `DELETE` | `/_kumostack/organizations/scps/{id}` | Delete an SCP |
| `GET` | `/_kumostack/sts/assume-role-log` | Real-time AssumeRole audit log |

```bash
# List all SCPs
curl http://localhost:4566/_kumostack/organizations/scps | jq .

# Update attachment
curl -X PATCH http://localhost:4566/_kumostack/organizations/scps/p-xxxxxxxx \
  -H "Content-Type: application/json" \
  -d '{"attachedTo": ["111111111111", "ou-eng"]}'

# View AssumeRole log
curl http://localhost:4566/_kumostack/sts/assume-role-log | jq .log
```
