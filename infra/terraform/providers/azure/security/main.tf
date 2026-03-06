locals {
  frontdoor_origin_name = "origin-${var.name_prefix}-api"
  frontdoor_route_name  = "route-${var.name_prefix}-api"
}

resource "azurerm_key_vault_secret" "openai_endpoint" {
  name         = "cna-azure-openai-endpoint"
  value        = var.azure_openai_endpoint
  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "appinsights_connection_string" {
  name         = "cna-applicationinsights-connection-string"
  value        = var.application_insights_connection_string
  key_vault_id = var.key_vault_id
}

resource "azurerm_role_assignment" "key_vault_secrets_officer" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_network_security_group" "platform" {
  name                = "nsg-${var.name_prefix}-platform"
  location            = var.location
  resource_group_name = var.resource_group_name
}

resource "azurerm_network_security_rule" "allow_api_ingress" {
  name                        = "allow-api-ingress"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefixes     = var.allowed_api_cidrs
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.platform.name
}

resource "azurerm_cdn_frontdoor_profile" "platform" {
  name                = "afd-${var.name_prefix}-platform"
  resource_group_name = var.resource_group_name
  sku_name            = "Standard_AzureFrontDoor"
}

resource "azurerm_cdn_frontdoor_endpoint" "platform" {
  name                     = "afd-endpoint-${var.name_prefix}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
}

resource "azurerm_cdn_frontdoor_origin_group" "api" {
  name                     = "og-${var.name_prefix}-api"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id

  load_balancing {}
  health_probe {
    interval_in_seconds = 120
    path                = "/health"
    protocol            = "Https"
    request_type        = "GET"
  }
}

resource "azurerm_cdn_frontdoor_origin" "api" {
  name                          = local.frontdoor_origin_name
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.api.id
  enabled                       = true
  host_name                     = var.api_container_app_fqdn
  http_port                     = 80
  https_port                    = 443
  origin_host_header            = var.api_container_app_fqdn
  priority                      = 1
  weight                        = 1000
  certificate_name_check_enabled = true
}

resource "azurerm_cdn_frontdoor_firewall_policy" "platform" {
  name                = "afd-waf-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  sku_name            = "Standard_AzureFrontDoor"
  mode                = "Prevention"

  managed_rule {
    type    = "DefaultRuleSet"
    version = "1.0"
    action  = "Block"
  }
}

resource "azurerm_cdn_frontdoor_route" "api" {
  name                          = local.frontdoor_route_name
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.platform.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.api.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.api.id]
  supported_protocols           = ["Http", "Https"]
  patterns_to_match             = ["/*"]
  forwarding_protocol           = "HttpsOnly"
  https_redirect_enabled        = true
  link_to_default_domain        = true
}

resource "azurerm_cdn_frontdoor_security_policy" "platform" {
  name                     = "afd-security-${var.name_prefix}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.platform.id

      association {
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.platform.id
        }

        patterns_to_match = ["/*"]
      }
    }
  }
}

resource "azurerm_role_assignment" "api_managed_identity_key_vault_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.managed_identity_principal_id
}
