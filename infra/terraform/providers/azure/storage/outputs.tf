output "storage_account_id" {
  value = azurerm_storage_account.this.id
}

output "storage_account_name" {
  value = azurerm_storage_account.this.name
}

output "primary_blob_endpoint" {
  value = azurerm_storage_account.this.primary_blob_endpoint
}

output "primary_web_endpoint" {
  value = azurerm_storage_account.this.primary_web_endpoint
}

output "container_names" {
  value = keys(azurerm_storage_container.containers)
}
output "container_resource_ids" {
  # azurerm 4.x: `id` now returns the ARM resource ID and resource_manager_id is
  # deprecated in favour of it (same value). Use `id` to avoid the deprecation
  # warning and stay forward-compatible with azurerm 5.x.
  value = { for k, v in azurerm_storage_container.containers : k => v.id }
}
