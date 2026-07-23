# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/compute/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: compute platform TBD (default direction: ECS on Fargate, matching Azure Container Apps' managed-container model -- see the layout discussion in issue #110).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

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

variable "name_prefix" {
  description = "Normalized name prefix for compute resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to compute resources"
  type        = map(string)
  default     = {}
  nullable    = false
}

# Mirrors Azure compute's container_app_min_replicas / container_app_max_replicas --
# kept as the stable cross-cloud scaling contract; ECS-specific fields (task CPU/
# memory, target group, service discovery) are added when the module is built out.
variable "min_count" {
  description = "Minimum task/service count"
  type        = number
  default     = 1
}

variable "max_count" {
  description = "Maximum task/service count"
  type        = number
  default     = 3
}
