variable "resource_group_name" {
  description = "Resource group name containing the Key Vault"
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
  description = "Managed identity principal ID used for Key Vault access"
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
  description = "API Container App resource ID"
  type        = string
}

variable "worker_container_app_id" {
  description = "Worker Container App resource ID"
  type        = string
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint"
  type        = string
}

variable "application_insights_connection_string" {
  description = "Application Insights connection string"
  type        = string
}

variable "allowed_api_cidrs" {
  description = "CIDR ranges allowed to reach the API front door"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
