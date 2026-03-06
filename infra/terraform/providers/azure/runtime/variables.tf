variable "resource_group_name" {
  description = "Resource group name for runtime wiring resources"
  type        = string
}

variable "storage_account_id" {
  description = "Storage account resource ID"
  type        = string
}

variable "storage_account_name" {
  description = "Storage account name"
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault resource ID"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "Principal ID for the user-assigned managed identity"
  type        = string
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL"
  type        = string
}

variable "application_insights_connection_string" {
  description = "Application Insights connection string"
  type        = string
  sensitive   = true
}

variable "api_container_app_id" {
  description = "Container App resource ID for CNA API"
  type        = string
}

variable "worker_container_app_id" {
  description = "Container App resource ID for CNA worker"
  type        = string
}
