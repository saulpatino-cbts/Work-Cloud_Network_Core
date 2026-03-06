output "openai_endpoint_secret_name" {
  value = azurerm_key_vault_secret.openai_endpoint.name
}

output "appinsights_connection_secret_name" {
  value = azurerm_key_vault_secret.appinsights_connection_string.name
}
