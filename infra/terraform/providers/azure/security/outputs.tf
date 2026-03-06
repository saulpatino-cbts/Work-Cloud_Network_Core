output "network_security_group_id" {
  description = "Network security group ID for platform ingress governance"
  value       = azurerm_network_security_group.platform.id
}
