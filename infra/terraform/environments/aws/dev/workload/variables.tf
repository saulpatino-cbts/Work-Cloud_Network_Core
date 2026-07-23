variable "project_name" {
  description = "Project name used in resource naming (mirrors Azure's var.project_name)"
  type        = string
  default     = "cna"
}

variable "environment" {
  description = "Deployment environment (dev or prod)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "region_short" {
  description = "Short region code used in resource naming (mirrors Azure's var.region_short)"
  type        = string
  default     = "use1"
}

variable "github_owner" {
  description = "GitHub organization/owner for the github provider"
  type        = string
  default     = "saulpatinojr"
}

variable "github_token" {
  description = "GitHub token for the github provider"
  type        = string
  sensitive   = true
  default     = ""
}

variable "api_image" {
  description = "Container image for CNA API"
  type        = string
  default     = "docker.io/example-namespace/cna:api-latest"
}

variable "worker_image" {
  description = "Container image for CNA worker"
  type        = string
  default     = "docker.io/example-namespace/cna:worker-latest"
}

variable "web_image" {
  description = "Container image for CNA Web (Next.js 15)"
  type        = string
  default     = "docker.io/example-namespace/cna:web-latest"
}
