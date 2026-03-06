output "network_security_group_id" {
  description = "Network security group ID for platform ingress governance"
  value       = azurerm_network_security_group.platform.id
}

output "frontdoor_endpoint_host_name" {
  description = "Azure Front Door endpoint hostname"
  value       = azurerm_cdn_frontdoor_endpoint.platform.host_name
}
