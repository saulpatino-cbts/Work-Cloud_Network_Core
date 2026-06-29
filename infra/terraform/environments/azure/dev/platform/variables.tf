variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "location" {
  description = "Azure region for CNA Platform deployment"
  type        = string
  default     = "southcentralus"
}

variable "region_short" {
  description = "Short region code used in resource names"
  type        = string
  default     = "scus"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "cna"
}

variable "vnet_address_space" {
  type    = list(string)
  default = ["10.40.0.0/16"]
}

variable "subnet_container_apps_infra_prefixes" {
  type    = list(string)
  default = ["10.40.0.0/23"]
}

variable "subnet_private_endpoints_prefixes" {
  type    = list(string)
  default = ["10.40.2.0/24"]
}

variable "subnet_database_prefixes" {
  type    = list(string)
  default = ["10.40.3.0/24"]
}

variable "subnet_firewall_prefixes" {
  type    = list(string)
  default = ["10.40.4.0/26"]
}

variable "manage_diagnostic_settings" {
  description = "Whether Terraform manages per-resource diagnostic settings. Defaults FALSE: on an Azure Landing Zone the DeployIfNotExists policy ('setByPolicy-*') already owns diagnostics, and managing our own races the policy's remediation (azurerm 'already exists / needs import'). Set true (TF_VAR_manage_diagnostic_settings / ALZ_DIAGNOSTICS_MANAGE) only on a non-governed subscription, or to dual-ship to a different workspace and accept the create-race."
  type        = bool
  default     = false
}
