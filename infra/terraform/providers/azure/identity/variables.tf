variable "resource_group_name" {
  description = "Resource group name for identity resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for identity resources"
  type        = string
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
}

variable "tags" {
  description = "Tags applied to identity resources"
  type        = map(string)
  default     = {}
}
