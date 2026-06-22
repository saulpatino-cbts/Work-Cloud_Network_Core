variable "resource_group_name" {
  description = "Resource group name for identity resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for identity resources"
  type        = string
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
}

variable "tags" {
  description = "Tags applied to identity resources"
  type        = map(string)
  default     = {}
}

# FinOps / Zero Trust — Key Vault hardening
variable "key_vault_soft_delete_retention_days" {
  description = "Soft-delete retention for Key Vault. Minimum 7 days; set to 90 when purge_protection is enabled."
  type        = number
  default     = 7
}

variable "key_vault_purge_protection_enabled" {
  description = "Enable purge protection on Key Vault. Required for prod — prevents accidental permanent deletion of secrets."
  type        = bool
  default     = false
}

variable "key_vault_name_suffix" {
  description = "Optional suffix appended to the Key Vault name. Increment (e.g. '2', '3') after a full teardown to avoid soft-delete name conflicts."
  type        = string
  default     = ""
}
