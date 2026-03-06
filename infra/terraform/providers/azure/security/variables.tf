variable "resource_group_name" {
  description = "Resource group name for security resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for security resources"
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault resource ID"
  type        = string
}

variable "key_vault_name" {
  description = "Key Vault name"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "Managed identity principal ID"
  type        = string
}

variable "managed_identity_id" {
  description = "Managed identity resource ID"
  type        = string
}

variable "managed_identity_client_id" {
  description = "Managed identity client ID"
  type        = string
}

variable "api_container_app_id" {
  description = "Container App resource ID for CNA API"
  type        = string
}

variable "worker_container_app_id" {
  description = "Container App resource ID for CNA worker"
  type        = string
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint"
  type        = string
}

variable "application_insights_connection_string" {
  description = "Application Insights connection string"
  type        = string
  sensitive   = true
}
