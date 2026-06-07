# ─────────────────────────────────────────────────────────────────────────────
# S3 + CloudFront Static Website (production pattern)
#
# Architecture:
#   Browser → CloudFront (CDN / HTTPS) → S3 bucket (private, OAC)
#
# The S3 bucket is NOT public. Only CloudFront can read it via the
# Origin Access Control policy. This is the AWS-recommended approach.
# ─────────────────────────────────────────────────────────────────────────────

# ── S3 bucket (private) ───────────────────────────────────────────────────────
resource "aws_s3_bucket" "website" {
  bucket        = var.bucket_name
  force_destroy = true
}

# Keep bucket PRIVATE — block all public access
resource "aws_s3_bucket_public_access_block" "website" {
  bucket = aws_s3_bucket.website.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── CloudFront Origin Access Control (OAC) ───────────────────────────────────
# OAC allows CloudFront to sign requests to S3 — the modern replacement for OAI
resource "aws_cloudfront_origin_access_control" "website" {
  name                              = "${var.bucket_name}-oac"
  description                       = "OAC for ${var.bucket_name} static website"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ── CloudFront distribution ───────────────────────────────────────────────────
resource "aws_cloudfront_distribution" "website" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "Static website — ${var.bucket_name}"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id                = "S3-${var.bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.website.id
  }

  default_cache_behavior {
    target_origin_id       = "S3-${var.bucket_name}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    # Cache for 1 hour in prod; set to 0 for local dev so refreshes are instant
    min_ttl     = 0
    default_ttl = var.cloudfront_ttl
    max_ttl     = var.cloudfront_ttl
  }

  # Return index.html for SPA-style 403/404 from S3
  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/error.html"
    error_caching_min_ttl = 0
  }
  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/error.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  depends_on = [aws_s3_bucket_public_access_block.website]
}

# ── S3 bucket policy: allow ONLY CloudFront OAC ───────────────────────────────
resource "aws_s3_bucket_policy" "website" {
  bucket = aws_s3_bucket.website.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::${var.bucket_name}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.website.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.website]
}

# ── Upload all files from www/ ────────────────────────────────────────────────
locals {
  content_types = {
    ".html" = "text/html"
    ".css"  = "text/css"
    ".js"   = "application/javascript"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".svg"  = "image/svg+xml"
    ".ico"  = "image/x-icon"
    ".json" = "application/json"
    ".woff2"= "font/woff2"
    ".woff" = "font/woff"
  }
}

resource "aws_s3_object" "website_files" {
  for_each = fileset("${path.module}/www", "**")

  bucket       = aws_s3_bucket.website.id
  key          = each.value
  source       = "${path.module}/www/${each.value}"
  content_type = lookup(local.content_types, regex("\\.[^.]+$", each.value), "application/octet-stream")
  etag         = filemd5("${path.module}/www/${each.value}")
}
