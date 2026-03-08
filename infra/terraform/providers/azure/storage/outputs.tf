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
