variable "resource_group_name" {
  description = "Resource group name for runtime wiring resources"
  type        = string
}

variable "storage_account_id" {
  description = "Storage account resource ID"
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault resource ID — secrets are stored here for sync-env workflow"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "Principal ID for the user-assigned managed identity"
  type        = string
}

variable "database_url" {
  description = "Full PostgreSQL connection string (postgresql://user:pass@host:5432/db?sslmode=require)"
  type        = string
  sensitive   = true
}

variable "nextauth_secret" {
  description = "NextAuth.js JWT signing secret — generate with: openssl rand -base64 32"
  type        = string
  sensitive   = true
}

variable "entra_client_secret" {
  description = "Entra ID (Azure AD) OAuth2 client secret for NextAuth provider"
  type        = string
  sensitive   = true
}
