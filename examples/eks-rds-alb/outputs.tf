# ── RDS ───────────────────────────────────────────────────────────────────────

output "rds_endpoint" {
  value       = "${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}"
  description = "PostgreSQL endpoint — use with psql"
}

output "rds_address" {
  value       = aws_db_instance.postgres.address
  description = "PostgreSQL host"
}

output "rds_port" {
  value       = aws_db_instance.postgres.port
  description = "PostgreSQL port"
}

output "psql_cmd" {
  value       = "psql -h ${aws_db_instance.postgres.address} -p ${aws_db_instance.postgres.port} -U ${var.db_username} -d ${var.db_name}"
  description = "Ready-to-run psql command"
}

# ── Secrets Manager ───────────────────────────────────────────────────────────

output "secret_arn" {
  value       = aws_secretsmanager_secret.db_credentials.arn
  description = "Secrets Manager secret ARN"
}

output "secret_name" {
  value       = aws_secretsmanager_secret.db_credentials.name
  description = "Secrets Manager secret name"
}

output "get_secret_cmd" {
  value       = "aws secretsmanager get-secret-value --secret-id ${var.secret_name} --endpoint-url http://localhost:4566 --query SecretString --output text"
  description = "Command to retrieve the secret"
}

# ── EKS ───────────────────────────────────────────────────────────────────────

output "eks_cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "EKS cluster name"
}

output "eks_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "EKS cluster API endpoint (https://localhost:<port>)"
}

output "eks_ca_cert" {
  value       = aws_eks_cluster.main.certificate_authority[0].data
  description = "Base64-encoded cluster CA certificate"
  sensitive   = true
}

output "kubeconfig_cmd" {
  value       = "bash kubeconfig.sh   # generates ~/.kube/config entry for context 'kumostack'"
  description = "How to configure kubectl"
}

# ── ALB ───────────────────────────────────────────────────────────────────────

output "alb_arn" {
  value       = aws_lb.main.arn
  description = "ALB ARN"
}

output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "ALB DNS name (API-emulated — does not proxy real traffic)"
}

# ── Frontend ──────────────────────────────────────────────────────────────────

output "cloudfront_domain" {
  value       = aws_cloudfront_distribution.frontend.domain_name
  description = "CloudFront distribution domain"
}

output "frontend_bucket" {
  value       = aws_s3_bucket.frontend.id
  description = "S3 bucket for frontend static assets"
}

# ── Architecture summary ──────────────────────────────────────────────────────

output "architecture" {
  value = <<-EOT
    CloudFront (cdn)   → ${aws_cloudfront_distribution.frontend.domain_name}
      ├─ origin (S3)   → ${aws_s3_bucket.frontend.id}
      └─ origin (ALB)  → ${aws_lb.main.dns_name}
    ALB  (emulated)    → ${aws_lb.main.dns_name}
    EKS  (real k3s)    → ${aws_eks_cluster.main.endpoint}
    RDS  (real pg)     → ${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}
    Secret             → ${aws_secretsmanager_secret.db_credentials.name}
  EOT
  description = "Deployed architecture summary"
}
