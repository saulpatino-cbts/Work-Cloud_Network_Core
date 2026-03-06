variable "resource_group_name" {
  description = "Resource group name for compute resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for compute resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to compute resources"
  type        = map(string)
  default     = {}
}
