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

output "container_app_environment_id" {
  value = module.compute.container_app_environment_id
}

output "api_fqdn" {
  value = module.compute.api_fqdn
}

output "worker_name" {
  value = module.compute.worker_name
}

output "azure_openai_account_name" {
  value = module.ai.azure_openai_account_name
}

output "azure_openai_endpoint" {
  value = module.ai.azure_openai_endpoint
}

output "application_insights_name" {
  value = module.ai.application_insights_name
}
