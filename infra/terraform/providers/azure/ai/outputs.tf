output "application_insights_name" {
  value = azurerm_application_insights.this.name
}

output "application_insights_id" {
  value = azurerm_application_insights.this.id
}

output "application_insights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}

output "foundry_resource_group_name" {
  value = var.resource_group_name
}

output "foundry_account_id" {
  value = azurerm_cognitive_account.foundry.id
}

output "foundry_account_name" {
  value = azurerm_cognitive_account.foundry.name
}

output "foundry_endpoint" {
  value = azurerm_cognitive_account.foundry.endpoint
}

output "foundry_project_id" {
  value = azapi_resource.foundry_project.id
}

output "foundry_project_name" {
  value = var.foundry_project_name
}

output "foundry_claude_messages_endpoint" {
  value = "https://${azurerm_cognitive_account.foundry.custom_subdomain_name}.services.ai.azure.com/anthropic/v1/messages"
}
