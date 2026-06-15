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

variable "web_image" {
  description = "Container image for CNA Web (Next.js 15)"
  type        = string
  default     = "ghcr.io/saulpatinojr/cna-web:latest"
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

variable "ghcr_username" {
  description = "GitHub username (or org) for GHCR image pulls. Must match the package owner."
  type        = string
  default     = ""
}

variable "ghcr_pat" {
  description = "GitHub PAT with read:packages scope for GHCR image pulls. Required for private GHCR packages."
  type        = string
  sensitive   = true
  default     = ""
}

variable "container_app_min_replicas" {
  description = "Minimum replicas for Container Apps"
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
  description = "Retention period for Log Analytics workspace. Use 30 for dev, 90 for prod (compliance)."
  type        = number
  default     = 30
}

# FinOps: scale-to-zero for idle environments
variable "enable_scale_to_zero" {
  description = "Override min_replicas to 0 for all Container Apps. Major cost saving for dev (no charge when idle). Not recommended for prod — adds cold-start latency."
  type        = bool
  default     = false
}

variable "api_target_port" {
  description = "Ingress target port for API container app"
  type        = number
  default     = 80
}

variable "web_target_port" {
  description = "Ingress target port for web container app (Next.js)"
  type        = number
  default     = 3000
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

variable "web_env_vars" {
  description = "Plain environment variables for the web container app"
  type        = map(string)
  default     = {}
}

variable "api_secret_env_vars" {
  description = "Secret-backed env vars for the API Container App. Map key is env var name, value is secret name."
  type        = map(string)
  default     = {}
}

variable "worker_secret_env_vars" {
  description = "Secret-backed env vars for the worker Container App. Map key is env var name, value is secret name."
  type        = map(string)
  default     = {}
}

variable "web_secret_env_vars" {
  description = "Secret-backed env vars for the web Container App. Map key is env var name, value is secret name."
  type        = map(string)
  default     = {}
}

variable "container_app_secrets" {
  description = "Secrets injected into all Container Apps. Map key is secret name, value is secret value."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "container_apps_internal_only" {
  description = "Whether the Container Apps environment should use an internal load balancer. Set false to allow the web Container App to have external ingress."
  type        = bool
  default     = false
}

variable "container_apps_public_network_access" {
  description = "Public network access mode for the Container Apps environment. Set to Disabled when Azure Front Door reaches the app over Private Link."
  type        = string
  default     = "Enabled"

  validation {
    condition     = contains(["Enabled", "Disabled"], var.container_apps_public_network_access)
    error_message = "container_apps_public_network_access must be Enabled or Disabled."
  }
}

variable "container_app_environment_workload_profiles" {
  description = "Optional workload profiles for the Container Apps environment. Required for features such as Azure Front Door Private Link origins."
  type = list(object({
    name                  = string
    workload_profile_type = string
    minimum_count         = optional(number)
    maximum_count         = optional(number)
  }))
  default = []
}

variable "web_ingress_ip_security_restrictions" {
  description = "Optional IP-based ingress restrictions for the public web Container App. Use this to constrain direct-origin access when the selected edge pattern cannot yet use private origins."
  type = list(object({
    name             = string
    action           = string
    ip_address_range = string
    description      = optional(string)
  }))
  default = []
}

variable "infrastructure_subnet_id" {
  description = "Subnet ID delegated to the Container Apps managed environment infrastructure"
  type        = string
  default     = null
}
