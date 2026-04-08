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
  description = "CNA API Container App FQDN (internal — not directly reachable from internet)"
  value       = module.compute.api_fqdn
}

output "web_fqdn" {
  description = "CNA Web (Next.js) Container App FQDN (accessed via Front Door, not directly)"
  value       = module.compute.web_fqdn
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

output "storage_role_assignment_id" {
  value = module.runtime.storage_role_assignment_id
}

output "presentation_cdn_fqdn" {
  value = module.presentation.cdn_fqdn
}

output "frontdoor_endpoint_host_name" {
  description = "Azure Front Door endpoint hostname — public entry point for the prod platform"
  value       = module.security.frontdoor_endpoint_host_name
}

output "openai_endpoint_secret_name" {
  value = module.security.openai_endpoint_secret_name
}

output "database_server_name" {
  description = "PostgreSQL Flexible Server name"
  value       = module.database.server_name
}

output "database_server_fqdn" {
  description = "PostgreSQL Flexible Server FQDN (private DNS — only reachable within the VNet)"
  value       = module.database.server_fqdn
}
