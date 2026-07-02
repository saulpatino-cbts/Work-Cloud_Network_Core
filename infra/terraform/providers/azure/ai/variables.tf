variable "resource_group_name" {
  description = "Workload resource group name for observability resources."
  type        = string
}

variable "location" {
  description = "Azure location for App Insights, matching the workload resource group."
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for AI resources."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "tags" {
  description = "Tags applied to AI resources."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "foundry_location" {
  description = "Azure region for Microsoft Foundry resources."
  type        = string
  default     = "eastus2"
}

variable "foundry_account_name" {
  description = "Microsoft Foundry AI Services account name."
  type        = string
}

variable "foundry_project_name" {
  description = "Microsoft Foundry project name."
  type        = string
}

variable "chat_deployment_enabled" {
  description = "Create the chat model deployment on the Foundry account. Off by default so existing consumers opt in explicitly (AVM TFNFR34)."
  type        = bool
  default     = false
  nullable    = false
}

variable "chat_deployment_name" {
  description = "Deployment (alias) name the app references via AZURE_OPENAI_DEPLOYMENT."
  type        = string
  default     = "gpt-chat-latest"
}

variable "chat_model_name" {
  description = "Underlying OpenAI model for the chat deployment. gpt-4.1 and all *-chat variants are in Deprecating state as of 2026-07; gpt-5.4 is GA with GlobalStandard quota in this subscription."
  type        = string
  default     = "gpt-5.4"
}

variable "chat_model_version" {
  description = "Model version for the chat deployment. gpt-5.4 2026-03-05 is GA (inference supported through 2027-03)."
  type        = string
  default     = "2026-03-05"
}

variable "chat_deployment_sku_name" {
  description = "Deployment SKU/type: Standard, GlobalStandard, DataZoneStandard, ProvisionedManaged."
  type        = string
  default     = "GlobalStandard"
}

variable "chat_deployment_capacity" {
  description = "Deployment capacity in 1K-TPM units (100 = 100K tokens/min). Sized for the sectioned Comprehensive Assessment generator (concurrent section calls) plus chat/analysis traffic."
  type        = number
  default     = 100
}
