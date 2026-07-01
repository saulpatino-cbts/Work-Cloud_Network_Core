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
