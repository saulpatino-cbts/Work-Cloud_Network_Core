output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "location" {
  value = azurerm_resource_group.this.location
}

output "storage_account_name" {
  value = module.storage.storage_account_name
}

output "storage_web_endpoint" {
  value = module.storage.primary_web_endpoint
}

output "key_vault_name" {
  value = module.identity.key_vault_name
}

output "managed_identity_client_id" {
  value = module.identity.managed_identity_client_id
}
