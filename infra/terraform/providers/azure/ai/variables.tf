variable "resource_group_name" {
  description = "Resource group name for AI resources"
  type        = string
}

variable "location" {
  description = "Azure location for App Insights (matches the workload RG)"
  type        = string
}

variable "openai_location" {
  description = "Azure region for the Azure OpenAI cognitive account. Defaults to var.location but can be overridden when the target model is only available in specific regions (e.g. eastus2 for gpt-5.x)."
  type        = string
  default     = ""
}

variable "name_prefix" {
  description = "Normalized name prefix for AI resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to AI resources"
  type        = map(string)
  default     = {}
}

variable "application_type" {
  description = "Application Insights application type"
  type        = string
  default     = "web"
}

# ─── Model configuration ───────────────────────────────────────────────────────
# Set at the environment level (dev/prod main.tf) so upgrading the model only
# requires changing values there, not editing this module.

variable "openai_model_name" {
  description = "Azure OpenAI model to deploy (e.g. gpt-5.4, gpt-4o)"
  type        = string
  default     = "gpt-5.4"
}

variable "openai_model_version" {
  description = "Exact model version as listed in az cognitiveservices account list-models"
  type        = string
  default     = "2026-03-05"
}

variable "openai_api_version" {
  description = "Azure OpenAI REST API version used by the application (e.g. 2026-04-01-preview)"
  type        = string
  default     = "2026-04-01-preview"
}

variable "openai_deployment_capacity" {
  description = "Provisioned tokens-per-minute in thousands (e.g. 30 = 30K TPM)"
  type        = number
  default     = 30
}
