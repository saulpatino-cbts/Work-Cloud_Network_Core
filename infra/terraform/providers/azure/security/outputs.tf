output "frontdoor_endpoint_host_name" {
  description = "Azure Front Door endpoint hostname"
  value       = azurerm_cdn_frontdoor_endpoint.platform.host_name
}

output "frontdoor_profile_id" {
  description = "Azure Front Door profile resource ID"
  value       = azurerm_cdn_frontdoor_profile.platform.id
}

output "frontdoor_endpoint_id" {
  description = "Azure Front Door endpoint resource ID"
  value       = azurerm_cdn_frontdoor_endpoint.platform.id
}

output "frontdoor_origin_group_id" {
  description = "Azure Front Door origin group resource ID"
  value       = azurerm_cdn_frontdoor_origin_group.web.id
}

output "frontdoor_origin_id" {
  description = "Azure Front Door origin resource ID"
  value       = azurerm_cdn_frontdoor_origin.web.id
}

output "frontdoor_route_id" {
  description = "Azure Front Door route resource ID"
  value       = azurerm_cdn_frontdoor_route.web.id
}

output "frontdoor_custom_domain_id" {
  description = "Azure Front Door custom domain resource ID when configured"
  value       = local.use_custom_domain ? azurerm_cdn_frontdoor_custom_domain.platform[0].id : null
}

output "frontdoor_firewall_policy_id" {
  description = "Azure Front Door WAF policy resource ID"
  value       = azurerm_cdn_frontdoor_firewall_policy.platform.id
}

output "frontdoor_secret_id" {
  description = "Azure Front Door secret resource ID for customer-managed certificates when configured"
  value       = local.use_customer_managed_tls ? azurerm_cdn_frontdoor_secret.platform[0].id : null
}

output "postgres_private_dns_zone_id" {
  description = "Private DNS zone resource ID for PostgreSQL Flexible Server VNet integration"
  value       = azurerm_private_dns_zone.postgres.id
}
