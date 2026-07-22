# =============================================================================
# IAM Roles & Policies
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# ─── ECS Task Execution Role ─────────────────────────────────────────────────
# Allows ECS agent to pull images, write logs, read secrets
resource "aws_iam_role" "ecs_execution" {
  name = "${local.name_prefix}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_policy" "ecs_execution_secrets" {
  name = "${local.name_prefix}-ecs-execution-secrets"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.nextauth_secret.arn,
        aws_secretsmanager_secret.entra_client_secret.arn,
        aws_secretsmanager_secret.credential_encryption_key.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_execution_secrets.arn
}

# Docker Hub private registry access
resource "aws_iam_policy" "ecs_execution_dockerhub" {
  count = var.dockerhub_username != "" ? 1 : 0
  name  = "${local.name_prefix}-ecs-execution-dockerhub"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.dockerhub[0].arn]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_dockerhub" {
  count      = var.dockerhub_username != "" ? 1 : 0
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_execution_dockerhub[0].arn
}

# ─── ECS Task Role ───────────────────────────────────────────────────────────
# The application identity — what the running containers can access
resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "ecs_task_s3" {
  name = "${local.name_prefix}-ecs-task-s3"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.artifacts.arn,
        "${aws_s3_bucket.artifacts.arn}/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_s3" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task_s3.arn
}

resource "aws_iam_policy" "ecs_task_secrets_read" {
  name = "${local.name_prefix}-ecs-task-secrets"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        "arn:${data.aws_partition.current.partition}:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${local.name_prefix}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_secrets_read" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task_secrets_read.arn
}

# ─── GitHub Actions OIDC Deploy Role ──────────────────────────────────────────
# Equivalent to the Azure deploy service principal with OIDC federation.
# Carries ReadOnlyAccess + SecurityAudit + Billing Reader for assessment,
# plus write permissions scoped to CNA resources for Terraform apply.

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

resource "aws_iam_role" "github_deploy" {
  name = "${local.name_prefix}-github-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRoleWithWebIdentity"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${var.github_owner}/${var.github_repository}:ref:refs/heads/main",
            "repo:${var.github_owner}/${var.github_repository}:environment:${var.environment}"
          ]
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

# Assessment reader roles (equivalent to Azure Global Reader + Security Reader + Billing Reader)
resource "aws_iam_role_policy_attachment" "deploy_readonly" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "deploy_security_audit" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/SecurityAudit"
}

resource "aws_iam_role_policy_attachment" "deploy_billing_reader" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AWSBillingReadOnlyAccess"
}

# Deploy write permissions — scoped to CNA resources only
resource "aws_iam_policy" "deploy_write" {
  name = "${local.name_prefix}-deploy-write"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECSFullAccess"
        Effect = "Allow"
        Action = ["ecs:*"]
        Resource = ["*"]
        Condition = {
          StringEquals = { "aws:ResourceTag/Project" = var.project_name }
        }
      },
      {
        Sid    = "InfraManagement"
        Effect = "Allow"
        Action = [
          "ec2:*",
          "elasticloadbalancing:*",
          "rds:*",
          "s3:*",
          "secretsmanager:*",
          "cloudfront:*",
          "wafv2:*",
          "logs:*",
          "iam:*",
          "cloudwatch:*",
          "application-autoscaling:*"
        ]
        Resource = ["*"]
      },
      {
        Sid    = "TerraformState"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "deploy_write" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = aws_iam_policy.deploy_write.arn
}
