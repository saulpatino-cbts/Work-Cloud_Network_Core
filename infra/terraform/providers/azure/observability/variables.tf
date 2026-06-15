variable "log_analytics_workspace_id" {
  description = "Shared Log Analytics workspace ID that receives diagnostic logs and metrics."
  type        = string
}

variable "diagnostic_targets" {
  description = "Map of diagnostic target names to Azure resource IDs."
  type        = map(string)
}

variable "diagnostic_setting_name_prefix" {
  description = "Prefix used when naming diagnostic settings."
  type        = string
  default     = "diag"
}
