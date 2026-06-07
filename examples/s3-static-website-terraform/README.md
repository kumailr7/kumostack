# S3 + CloudFront Static Website — Terraform

Production-grade static website pattern: **private S3 bucket** served through
**CloudFront** with Origin Access Control (OAC).

Based on the [LocalStack S3 Static Website tutorial](https://docs.localstack.cloud/aws/tutorials/s3-static-website-terraform/).

## Architecture

```
Browser
  │
  ▼  (HTTPS / CDN caching)
CloudFront Distribution
  │  OAC — signs every request with SigV4
  ▼
S3 Bucket  (private — no public access)
  ├── index.html
  └── error.html
```

**Why CloudFront in front of S3?**

| | S3 alone | S3 + CloudFront |
|---|---|---|
| HTTPS | ✗ HTTP only | ✓ HTTPS + HTTP→HTTPS redirect |
| Bucket visibility | Must be **public** | Stays **private** (OAC) |
| CDN / caching | ✗ | ✓ Edge cache, `max_ttl` |
| Custom domain | Manual CNAME | ACM cert + Route53 alias |
| Error pages | Basic XML | Custom HTML (`error.html`) |
| Security | Anyone can hit S3 directly | Only CloudFront signed requests |

## Resources created

| Resource | Name |
|---|---|
| `aws_s3_bucket` | `kumostack-website` (private) |
| `aws_s3_bucket_public_access_block` | all blocks = `true` |
| `aws_cloudfront_origin_access_control` | `kumostack-website-oac` |
| `aws_cloudfront_distribution` | → S3 origin via OAC |
| `aws_s3_bucket_policy` | Allow only CloudFront service principal |
| `aws_s3_object` × N | All files from `www/` |

## Quick start

```bash
# 1. Start KumoStack
docker compose up -d

# 2. Deploy
cd examples/s3-static-website-terraform
terraform init
terraform apply -auto-approve

# 3. Open the website
open http://localhost:4566/kumostack-website/index.html
```

## Outputs

```
architecture      = "Browser → CloudFront (xxx.cloudfront.net) → S3 (private: kumostack-website)"
cloudfront_domain = "EPCK58Y2T3NJEA.cloudfront.net"
cloudfront_id     = "EPCK58Y2T3NJEA"
website_url       = "http://localhost:4566/kumostack-website/index.html"
```

## Customise

```bash
# Different bucket name
terraform apply -var="bucket_name=my-site"

# Production TTL (1 hour cache)
terraform apply -var="cloudfront_ttl=3600"
```

## Add more pages

Drop files in `www/` and run `terraform apply` — the `fileset()` loop
in `main.tf` uploads everything automatically with correct `content_type`.

## Tear down

```bash
terraform destroy -auto-approve
```

## File structure

```
s3-static-website-terraform/
├── provider.tf     # AWS provider → KumoStack (localhost:4566)
├── variables.tf    # bucket_name, cloudfront_ttl
├── main.tf         # S3 bucket + CloudFront dist + OAC + bucket policy + uploads
├── outputs.tf      # URLs and architecture summary
└── www/
    ├── index.html  # Home page
    └── error.html  # 404 page
```
