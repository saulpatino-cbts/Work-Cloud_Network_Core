variable "resource_group_name" {
  description = "Resource group name for database resources"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix"
  type        = string
}

variable "tags" {
  description = "Tags applied to database resources"
  type        = map(string)
  default     = {}
}

variable "admin_username" {
  description = "PostgreSQL administrator username"
  type        = string
  default     = "cnaadmin"
}

variable "admin_password" {
  description = "PostgreSQL administrator password — must be set from Key Vault or GitHub Secret"
  type        = string
  sensitive   = true
}

variable "db_subnet_id" {
  description = "Subnet ID delegated to Microsoft.DBforPostgreSQL/flexibleServers"
  type        = string
}

variable "postgres_private_dns_zone_id" {
  description = "Private DNS zone ID for privatelink.postgres.database.azure.com"
  type        = string
}

variable "sku_name" {
  description = "PostgreSQL Flexible Server SKU. Use B_Standard_B1ms for dev, GP_Standard_D2s_v3 for prod."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "storage_mb" {
  description = "Storage allocated in MB"
  type        = number
  default     = 32768
}

variable "backup_retention_days" {
  description = "Backup retention in days"
  type        = number
  default     = 7
}

variable "postgres_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "16"
}
