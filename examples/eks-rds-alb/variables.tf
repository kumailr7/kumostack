variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "kumostack-cluster"
}

variable "db_identifier" {
  description = "RDS instance identifier"
  type        = string
  default     = "myapp-postgres"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "appdb"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "appuser"
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  default     = "S3cr3tPass!"
  sensitive   = true
}

variable "secret_name" {
  description = "Secrets Manager secret name for DB credentials"
  type        = string
  default     = "rds/myapp/credentials"
}
