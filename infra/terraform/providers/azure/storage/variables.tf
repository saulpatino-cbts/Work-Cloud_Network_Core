variable "resource_group_name" {
  description = "Resource group name for storage resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for storage resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to storage resources"
  type        = map(string)
  default     = {}
  nullable    = false
}

# FinOps — replication and lifecycle
variable "replication_type" {
  description = "Storage account replication type. Use geo-replicated values for the curated Checkov gate."
  type        = string
  default     = "GZRS"
}

variable "raw_artifact_retention_days" {
  description = "Days before raw-artifacts blobs are moved to Cool tier. Set 0 to disable. FinOps: Cool tier is ~50% cheaper than Hot."
  type        = number
  default     = 30
}

variable "deliverable_retention_days" {
  description = "Days before deliverables blobs are moved to Cool tier. Set 0 to disable."
  type        = number
  default     = 90
}
