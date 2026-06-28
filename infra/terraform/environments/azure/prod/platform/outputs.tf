output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "location" {
  value = azurerm_resource_group.this.location
}

output "private_endpoint_subnet_prefix" {
  description = "CIDR prefix for the private endpoint subnet, used by post-deploy private DNS validation"
  value       = azurerm_subnet.private_endpoints.address_prefixes[0]
}

output "database_subnet_prefix" {
  description = "CIDR prefix for the PostgreSQL Flexible Server delegated subnet (used to derive the server's private IP)"
  value       = azurerm_subnet.database.address_prefixes[0]
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the platform Log Analytics workspace, consumed by the workload for Container App / app diagnostics."
  value       = azurerm_log_analytics_workspace.platform.id
}

output "log_analytics_workspace_workspace_id" {
  description = "Workspace GUID of the platform Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.platform.workspace_id
}

output "log_analytics_workspace_location" {
  description = "Azure region of the platform Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.platform.location
}
