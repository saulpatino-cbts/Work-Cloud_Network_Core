# =============================================================================
# Core
# =============================================================================
variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "cna"
}

variable "environment" {
  description = "Deployment environment (dev, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-2"
}

# =============================================================================
# Networking
# =============================================================================
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.40.0.0/16"
}

variable "azs" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-2a", "us-east-2b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (ALB, NAT Gateway)"
  type        = list(string)
  default     = ["10.40.0.0/24", "10.40.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (ECS tasks)"
  type        = list(string)
  default     = ["10.40.10.0/24", "10.40.11.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets (RDS)"
  type        = list(string)
  default     = ["10.40.20.0/24", "10.40.21.0/24"]
}

# =============================================================================
# Container Images
# =============================================================================
variable "api_image" {
  description = "Docker image for the API service"
  type        = string
  default     = "docker.io/example-namespace/cna:api-latest"
}

variable "worker_image" {
  description = "Docker image for the worker service"
  type        = string
  default     = "docker.io/example-namespace/cna:worker-latest"
}

variable "web_image" {
  description = "Docker image for the web (Next.js) service"
  type        = string
  default     = "docker.io/example-namespace/cna:web-latest"
}

# =============================================================================
# ECS
# =============================================================================
variable "api_cpu" {
  description = "CPU units for API task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Memory (MiB) for API task"
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  type    = number
  default = 512
}

variable "worker_memory" {
  type    = number
  default = 1024
}

variable "web_cpu" {
  type    = number
  default = 512
}

variable "web_memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  description = "Desired task count for each service (0 = scale to zero for dev)"
  type        = number
  default     = 1
}

# =============================================================================
# Database (RDS PostgreSQL)
# =============================================================================
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.small"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "cna"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "cnaadmin"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS"
  type        = bool
  default     = false
}

variable "db_backup_retention_period" {
  description = "Backup retention in days"
  type        = number
  default     = 7
}

# =============================================================================
# Authentication (Entra ID / NextAuth)
# =============================================================================
variable "entra_tenant_id" {
  description = "Azure AD / Entra ID tenant ID for SSO"
  type        = string
}

variable "entra_client_id" {
  description = "Entra ID application client ID"
  type        = string
}

variable "entra_client_secret" {
  description = "Entra ID OAuth2 client secret"
  type        = string
  sensitive   = true
}

variable "nextauth_secret" {
  description = "NextAuth.js JWT signing secret"
  type        = string
  sensitive   = true
}

variable "nextauth_url" {
  description = "Canonical URL for NextAuth callbacks (CloudFront domain)"
  type        = string
  default     = ""
}

# =============================================================================
# Credential Encryption
# =============================================================================
variable "credential_encryption_key" {
  description = "Base64-encoded 32-byte AES-256 key for stored credentials"
  type        = string
  sensitive   = true
}

# =============================================================================
# AI / OpenAI
# =============================================================================
variable "openai_api_key" {
  description = "OpenAI API key (or Azure OpenAI key if routing through a proxy)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_endpoint" {
  description = "OpenAI-compatible endpoint URL"
  type        = string
  default     = ""
}

variable "openai_deployment" {
  description = "Model deployment name"
  type        = string
  default     = "gpt-4"
}

# =============================================================================
# Docker Registry
# =============================================================================
variable "dockerhub_username" {
  description = "Docker Hub username for private image pulls"
  type        = string
  default     = ""
}

variable "dockerhub_token" {
  description = "Docker Hub access token"
  type        = string
  sensitive   = true
  default     = ""
}

# =============================================================================
# Domain / TLS
# =============================================================================
variable "domain_name" {
  description = "Custom domain name (optional). Leave empty to use CloudFront default domain."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN in us-east-1 for CloudFront (required if domain_name is set)"
  type        = string
  default     = ""
}

# =============================================================================
# GitHub
# =============================================================================
variable "github_owner" {
  description = "GitHub organization or user"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository name (without owner)"
  type        = string
}

variable "github_token" {
  description = "GitHub PAT for managing repository variables"
  type        = string
  sensitive   = true
}
