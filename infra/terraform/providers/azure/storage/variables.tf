variable "resource_group_name" {
  description = "Resource group name for storage resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for storage resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to storage resources"
  type        = map(string)
  default     = {}
}
