output "storage_role_assignment_id" {
  value = [for r in azurerm_role_assignment.storage_blob_data_contributor : r.id]
}

output "database_url_secret_name" {
  description = "Key Vault secret name for the PostgreSQL connection string"
  value       = azurerm_key_vault_secret.database_url.name
}

output "nextauth_secret_name" {
  description = "Key Vault secret name for the NextAuth signing secret"
  value       = azurerm_key_vault_secret.nextauth_secret.name
}

output "entra_client_secret_name" {
  description = "Key Vault secret name for the Entra ID client secret"
  value       = azurerm_key_vault_secret.entra_client_secret.name
}

output "local_admin_password_secret_name" {
  description = "Key Vault secret name for the break-glass local admin password hash, or null if not configured for this environment"
  value       = var.local_admin_password != null ? azurerm_key_vault_secret.local_admin_password[0].name : null
}
