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

output "openai_deployment_name" {
  value = azurerm_cognitive_deployment.model.name
}

output "openai_api_version" {
  description = "Azure OpenAI API version to use — consumed by environment env vars"
  value       = var.openai_api_version
}
