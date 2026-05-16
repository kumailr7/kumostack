# draw.io Architecture Diagrams

Design AWS architecture diagrams directly in your browser using the embedded draw.io editor.

draw.io runs at `http://localhost:8083` and is also accessible as the **Diagrams** tab in the Ministack dashboard.

---

## Open the editor

Navigate to the **Diagrams** tab in the dashboard sidebar, or go directly to `http://localhost:8083`.

The editor starts with a pre-built Ministack architecture template showing the full local stack:

- Ministack (LocalStack-compatible API)
- Grafana + Prometheus + Loki
- Vector log pipeline
- Garage cold storage
- Stackport resource browser

---

## AWS shape library

draw.io ships with official AWS icon sets. To enable them:

1. Click **Extras → Edit Diagram** or use the shape panel on the left
2. Click **Search Shapes** and type "AWS" or "Amazon"
3. Or enable the full library: **View → Shape Libraries → AWS**

Common AWS shape categories available:

| Category | Shapes |
|---|---|
| Compute | EC2, Lambda, ECS, EKS, Fargate |
| Storage | S3, EBS, EFS, Glacier |
| Database | RDS, DynamoDB, ElastiCache, Redshift |
| Networking | VPC, ALB, CloudFront, Route 53, API Gateway |
| Messaging | SQS, SNS, EventBridge, Kinesis |
| Security | IAM, Cognito, Secrets Manager, KMS |

---

## Save and export diagrams

**Save to file** — `File → Save` exports a `.drawio` XML file you can commit to your repo.

**Export as image** — `File → Export As → PNG / SVG / PDF`

**Embed in docs** — Export as SVG and reference it in your MkDocs pages:

```markdown
![Architecture](../assets/architecture.svg)
```

---

## Import an existing diagram

Drag and drop a `.drawio` or `.xml` file onto the canvas, or use **File → Import From → Device**.

---

## Keyboard shortcuts

| Action | Shortcut |
|---|---|
| Zoom in / out | `Ctrl +` / `Ctrl -` |
| Fit page | `Ctrl Shift H` |
| Select all | `Ctrl A` |
| Undo / Redo | `Ctrl Z` / `Ctrl Y` |
| Add shape | Double-click canvas |
| Connect shapes | Hover a shape → drag blue arrow |
| Format panel | `Ctrl E` |
