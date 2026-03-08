output "cdn_profile_name" {
  value = azurerm_cdn_profile.this.name
}

output "cdn_endpoint_name" {
  value = azurerm_cdn_endpoint.this.name
}

output "cdn_fqdn" {
  value = azurerm_cdn_endpoint.this.fqdn
}
