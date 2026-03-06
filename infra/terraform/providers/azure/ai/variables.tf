variable "resource_group_name" {
  description = "Resource group name for AI resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
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
