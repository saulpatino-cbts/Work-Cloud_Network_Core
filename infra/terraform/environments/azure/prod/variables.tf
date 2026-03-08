variable "api_image" {
  description = "Container image for CNA API"
  type        = string
  default     = "ghcr.io/saulpatinojr/cna-api:latest"
}

variable "worker_image" {
  description = "Container image for CNA worker"
  type        = string
  default     = "ghcr.io/saulpatinojr/cna-worker:latest"
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "location" {
  description = "Azure region for CNA Platform deployment"
  type        = string
  default     = "southcentralus"
}

variable "region_short" {
  description = "Short region code used in resource names (e.g. scus, eus2, wus2)"
  type        = string
  default     = "scus"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "cna"
}
