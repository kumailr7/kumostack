output "bucket_name" {
  value       = aws_s3_bucket.website.id
  description = "S3 bucket name (private — only CloudFront can read it)"
}

output "cloudfront_domain" {
  value       = aws_cloudfront_distribution.website.domain_name
  description = "CloudFront distribution domain name"
}

output "cloudfront_id" {
  value       = aws_cloudfront_distribution.website.id
  description = "CloudFront distribution ID"
}

output "website_url" {
  value       = "http://localhost:4566/${aws_s3_bucket.website.id}/index.html"
  description = "Direct S3 path-style URL (KumoStack dev access)"
}

output "architecture" {
  value       = "Browser → CloudFront (${aws_cloudfront_distribution.website.domain_name}) → S3 (private: ${aws_s3_bucket.website.id})"
  description = "Deployed architecture summary"
}
