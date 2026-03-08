output "application_insights_name" {
  value = azurerm_application_insights.this.name
}

output "application_insights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}

output "azure_openai_account_id" {
  value = azurerm_cognitive_account.this.id
}

output "azure_openai_account_name" {
  value = azurerm_cognitive_account.this.name
}

output "azure_openai_endpoint" {
  value = azurerm_cognitive_account.this.endpoint
}
