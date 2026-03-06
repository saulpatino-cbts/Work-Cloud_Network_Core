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

variable "resource_group_name" {
  description = "Resource group name for compute resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for compute resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to compute resources"
  type        = map(string)
  default     = {}
}

variable "container_registry_server" {
  description = "Container registry server used by Container Apps"
  type        = string
  default     = "ghcr.io"
}

variable "container_app_min_replicas" {
  description = "Minimum replicas for publicly exposed API container app"
  type        = number
  default     = 1
}

variable "container_app_max_replicas" {
  description = "Maximum replicas for Container Apps"
  type        = number
  default     = 3
}

variable "container_app_revision_mode" {
  description = "Revision mode for Container Apps"
  type        = string
  default     = "Single"
}

variable "log_analytics_retention_in_days" {
  description = "Retention period for Log Analytics workspace"
  type        = number
  default     = 30
}

variable "api_target_port" {
  description = "Ingress target port for API container app"
  type        = number
  default     = 80
}

variable "api_env_vars" {
  description = "Plain environment variables for the API container app"
  type        = map(string)
  default     = {}
}

variable "worker_env_vars" {
  description = "Plain environment variables for the worker container app"
  type        = map(string)
  default     = {}
}

variable "api_secret_env_vars" {
  description = "Secret-backed environment variables for the API container app. Map key is env var name and value is secret name defined in container app secrets."
  type        = map(string)
  default     = {}
}

variable "worker_secret_env_vars" {
  description = "Secret-backed environment variables for the worker container app. Map key is env var name and value is secret name defined in container app secrets."
  type        = map(string)
  default     = {}
}

variable "container_app_secrets" {
  description = "Secrets injected into Container Apps. Map key is secret name and value is secret value."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "container_apps_internal_only" {
  description = "Whether the Container Apps environment should use internal-only ingress"
  type        = bool
  default     = false
}
