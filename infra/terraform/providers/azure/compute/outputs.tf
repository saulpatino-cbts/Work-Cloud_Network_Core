output "container_app_environment_id" {
  value = azurerm_container_app_environment.this.id
}

output "api_id" {
  value = azurerm_container_app.api.id
}

output "api_name" {
  value = azurerm_container_app.api.name
}

output "api_fqdn" {
  value = azurerm_container_app.api.latest_revision_fqdn
}

output "worker_id" {
  value = azurerm_container_app.worker.id
}

output "worker_name" {
  value = azurerm_container_app.worker.name
}

output "web_id" {
  description = "CNA Web (Next.js) Container App resource ID"
  value       = azurerm_container_app.web.id
}

output "web_name" {
  description = "CNA Web (Next.js) Container App name"
  value       = azurerm_container_app.web.name
}

output "web_fqdn" {
  description = "CNA Web (Next.js) Container App FQDN — used as Azure Front Door origin"
  value       = azurerm_container_app.web.latest_revision_fqdn
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.compute.id
}
