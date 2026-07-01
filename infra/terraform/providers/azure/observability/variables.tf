variable "log_analytics_workspace_id" {
  description = "Shared Log Analytics workspace ID that receives diagnostic logs and metrics."
  type        = string
}

variable "log_analytics_workspace_workspace_id" {
  description = "Workspace GUID used by Azure traffic analytics integrations."
  type        = string
}

variable "log_analytics_workspace_location" {
  description = "Azure region for the shared Log Analytics workspace."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that owns the observability helper resources."
  type        = string
}

variable "location" {
  description = "Azure region for observability helper resources."
  type        = string
}

variable "tags" {
  description = "Tags applied to observability helper resources."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "diagnostic_targets" {
  description = "Map of diagnostic target names to Azure resource IDs."
  type        = map(string)
  nullable    = false
}

variable "manage_diagnostic_settings" {
  description = "Whether Terraform manages per-resource diagnostic settings. Defaults FALSE: let an ALZ DeployIfNotExists policy own diagnostics (avoids the azurerm create-race with the policy's 'setByPolicy-*' setting). Set true only on a non-governed subscription, or to dual-ship to a separate workspace."
  type        = bool
  default     = false
}

variable "diagnostic_settings_settle_duration" {
  description = "Stabilization delay before creating diagnostic settings, allowing target resources to finish provisioning and any ALZ DeployIfNotExists diagnostic-settings remediation to settle. Prevents the azurerm create-race 'already exists' error on policy-governed subscriptions. 90s gives ALZ policy remediation ample time on busy subscriptions."
  type        = string
  default     = "90s"
}

variable "diagnostic_setting_name_prefix" {
  description = "Prefix used when naming diagnostic settings."
  type        = string
  default     = "diag"
}

variable "flow_log_target_resource_id" {
  description = "Resource ID of the virtual network whose traffic should be captured by flow logs. Required only when enable_virtual_network_flow_logs is true."
  type        = string
  default     = null
}

variable "flow_log_storage_account_id" {
  description = "Storage account used by Azure Network Watcher flow logs. Required only when enable_virtual_network_flow_logs is true."
  type        = string
  default     = null
}

variable "enable_virtual_network_flow_logs" {
  description = "Enable virtual network flow logs for the environment virtual network."
  type        = bool
  default     = false
}

variable "flow_log_retention_days" {
  description = "Retention period for virtual network flow logs."
  type        = number
  default     = 30
}

variable "flow_log_traffic_analytics_interval" {
  description = "Traffic Analytics interval in minutes for virtual network flow logs."
  type        = number
  default     = 10
}
