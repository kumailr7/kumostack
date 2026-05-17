# ─────────────────────────────────────────────────────────────────────────────
# EKS + RDS (PostgreSQL) + ALB + Secrets Manager
#
# What is REAL vs emulated in KumoStack:
#   RDS       → REAL Docker container (postgres:17-alpine), psql works
#   EKS       → REAL k3s cluster in Docker, kubectl works
#   Secrets   → REAL API, GetSecretValue returns exact stored JSON
#   ALB       → API-emulated (ARN/DNS returned, no actual traffic proxy)
# ─────────────────────────────────────────────────────────────────────────────

# ── IAM roles (KumoStack emulates IAM — these return real ARNs) ───────────────

resource "aws_iam_role" "eks_cluster" {
  name = "${var.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role" "eks_nodegroup" {
  name = "${var.cluster_name}-nodegroup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

# ── RDS PostgreSQL (REAL Docker container) ────────────────────────────────────

resource "aws_db_instance" "postgres" {
  identifier        = var.db_identifier
  engine            = "postgres"
  engine_version    = "17"
  instance_class    = "db.t3.micro"
  allocated_storage = 20

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  skip_final_snapshot = true
  publicly_accessible = true

  tags = {
    Name        = "${var.cluster_name}-postgres"
    Environment = "local"
  }
}

# ── Secrets Manager: store RDS credentials ────────────────────────────────────
# GetSecretValue returns the exact JSON you store here — your app parses it
# to get host/port/username/password without hardcoding anything.

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = var.secret_name
  description = "RDS PostgreSQL credentials for ${var.db_name}"

  tags = {
    App = var.cluster_name
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    dbname   = var.db_name
    username = var.db_username
    password = var.db_password
  })
}

# ── EKS Cluster (REAL k3s Kubernetes cluster in Docker) ───────────────────────
# After apply, run: bash kubeconfig.sh → kubectl get nodes

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.31"

  vpc_config {
    subnet_ids = ["subnet-00000000"]
  }

  tags = {
    Name        = var.cluster_name
    Environment = "local"
  }

  depends_on = [aws_iam_role.eks_cluster]
}

# ── EKS Node Group ────────────────────────────────────────────────────────────

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-nodes"
  node_role_arn   = aws_iam_role.eks_nodegroup.arn
  subnet_ids      = ["subnet-00000000"]
  instance_types  = ["t3.medium"]

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 2
  }

  tags = {
    Name = "${var.cluster_name}-nodes"
  }

  depends_on = [
    aws_eks_cluster.main,
    aws_iam_role.eks_nodegroup,
  ]
}

# ── ALB (API-emulated — CreateLoadBalancer returns real ARN + DNS) ────────────
# Note: KumoStack's ALB does not proxy HTTP traffic.
# Use the EKS endpoint directly for real requests.

resource "aws_lb" "main" {
  name               = "${var.cluster_name}-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-00000000", "subnet-00000001"]

  tags = {
    Name        = "${var.cluster_name}-alb"
    Environment = "local"
  }
}

resource "aws_lb_target_group" "app" {
  name        = "${var.cluster_name}-tg"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = "vpc-00000000"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 30
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
