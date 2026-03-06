output "container_app_environment_id" {
  value = azurerm_container_app_environment.this.id
}

output "api_name" {
  value = azurerm_container_app.api.name
}

output "api_fqdn" {
  value = azurerm_container_app.api.latest_revision_fqdn
}

output "worker_name" {
  value = azurerm_container_app.worker.name
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.compute.id
}
