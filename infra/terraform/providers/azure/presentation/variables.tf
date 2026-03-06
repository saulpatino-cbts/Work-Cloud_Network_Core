variable "resource_group_name" {
  description = "Resource group name for presentation resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for presentation resources"
  type        = string
}

variable "storage_account_id" {
  description = "Storage account ID for static website and artifact delivery"
  type        = string
}

variable "storage_account_name" {
  description = "Storage account name for static website and artifact delivery"
  type        = string
}

variable "tags" {
  description = "Tags applied to presentation resources"
  type        = map(string)
  default     = {}
}
