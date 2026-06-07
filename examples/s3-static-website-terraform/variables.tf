variable "bucket_name" {
  description = "Name of the S3 bucket to create for the static website"
  type        = string
  default     = "kumostack-website"
}

variable "cloudfront_ttl" {
  description = "CloudFront default/max TTL in seconds. Set to 0 for local dev (instant cache invalidation)."
  type        = number
  default     = 0
}
