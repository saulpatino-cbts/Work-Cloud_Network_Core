locals {
  frontdoor_origin_name      = "${var.name_prefix}-afd-origin"
  frontdoor_route_name       = "${var.name_prefix}-afd-route"
  use_custom_domain          = var.frontdoor_custom_domain_host_name != ""
  use_custom_domain_dns_zone = local.use_custom_domain && var.frontdoor_custom_domain_dns_zone_id != null
  use_customer_managed_tls   = var.frontdoor_secret_versionless_id != null && var.frontdoor_certificate_type == "CustomerCertificate"
}

resource "azurerm_key_vault_secret" "appinsights_connection_string" {
  name            = "cna-applicationinsights-connection-string"
  value           = var.application_insights_connection_string
  key_vault_id    = var.key_vault_id
  content_type    = "Application Insights connection string"
  expiration_date = var.secret_expiration_date
}

resource "azurerm_role_assignment" "key_vault_secrets_officer" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_network_security_group" "platform" {
  name                = "${var.name_prefix}-nsg"
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

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone" "keyvault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = var.resource_group_name
}

# PostgreSQL Flexible Server requires a dedicated private DNS zone and VNet link.
# The database module depends on this zone ID being available before the server is created.
resource "azurerm_private_dns_zone" "postgres" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "${var.name_prefix}-pdns-blob"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = var.virtual_network_id
}

resource "azurerm_private_dns_zone_virtual_network_link" "keyvault" {
  name                  = "${var.name_prefix}-pdns-kv"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.keyvault.name
  virtual_network_id    = var.virtual_network_id
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = "${var.name_prefix}-pdns-pg"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = var.virtual_network_id
}

resource "azurerm_private_endpoint" "storage_blob" {
  name                = "${var.name_prefix}-pep-blob"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "${var.name_prefix}-pep-psc-blob"
    private_connection_resource_id = var.storage_account_id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-storage-blob"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_private_endpoint" "keyvault" {
  name                = "${var.name_prefix}-pep-kv"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "${var.name_prefix}-pep-psc-kv"
    private_connection_resource_id = var.key_vault_id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-keyvault"
    private_dns_zone_ids = [azurerm_private_dns_zone.keyvault.id]
  }
}

resource "azurerm_cdn_frontdoor_profile" "platform" {
  name                = "${var.name_prefix}-afd"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"
}

resource "azurerm_cdn_frontdoor_secret" "platform" {
  count                    = local.use_customer_managed_tls ? 1 : 0
  name                     = "${var.name_prefix}-afd-cert"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id

  secret {
    customer_certificate {
      key_vault_certificate_id = var.frontdoor_secret_versionless_id
    }
  }
}

resource "azurerm_cdn_frontdoor_endpoint" "platform" {
  name                     = "${var.name_prefix}-afd-ep"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
}

resource "azurerm_cdn_frontdoor_origin_group" "web" {
  name                     = "${var.name_prefix}-afd-og"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id

  load_balancing {}
  health_probe {
    interval_in_seconds = 120
    path                = "/api/health"
    protocol            = "Https"
    request_type        = "GET"
  }
}

resource "azurerm_cdn_frontdoor_origin" "web" {
  name                           = local.frontdoor_origin_name
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.web.id
  enabled                        = true
  host_name                      = var.web_container_app_fqdn
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = var.web_container_app_fqdn
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true
}

resource "azurerm_cdn_frontdoor_custom_domain" "platform" {
  count                    = local.use_custom_domain ? 1 : 0
  name                     = "${var.name_prefix}-afd-domain"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
  dns_zone_id              = local.use_custom_domain_dns_zone ? var.frontdoor_custom_domain_dns_zone_id : null
  host_name                = var.frontdoor_custom_domain_host_name

  tls {
    certificate_type        = var.frontdoor_certificate_type
    minimum_tls_version     = var.frontdoor_minimum_tls_version
    cdn_frontdoor_secret_id = local.use_customer_managed_tls ? azurerm_cdn_frontdoor_secret.platform[0].id : null
  }
}

resource "azurerm_cdn_frontdoor_firewall_policy" "platform" {
  # Azure requires WAF policy names to be alphanumeric only — no hyphens allowed.
  name                = "${replace(var.name_prefix, "-", "")}fdfp"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"
  mode                = "Prevention"

  # ── Custom Allow rule (evaluated BEFORE managed rules) ──────────────────────
  # Auth.js v5 Server Actions POST to /auth/signin with a Next-Action header
  # and text/plain body — both of which trigger OWASP anomaly scoring rules in
  # DefaultRuleSet 1.0. The OAuth callback arrives at /api/auth/callback/* with
  # long JWT-like ?code= and ?state= params that trigger SQLI rules.
  #
  # An "Allow" custom rule terminates WAF evaluation immediately: managed rules
  # never inspect the request. This is the correct pattern for auth routes that
  # use their own PKCE/state/CSRF protection and do not need WAF scrutiny.
  custom_rule {
    name     = "AllowAuthPaths"
    enabled  = true
    priority = 10
    type     = "MatchRule"
    action   = "Allow"

    match_condition {
      match_variable     = "RequestUri"
      operator           = "BeginsWith"
      negation_condition = false
      match_values = [
        "/auth/",
        "/api/auth/",
      ]
    }
  }

  managed_rule {
    type    = "DefaultRuleSet"
    version = "1.0"
    action  = "Block"

    # Belt-and-suspenders exclusions for OAuth callback params and Auth.js
    # cookies — these back-stop the custom Allow rule in case path matching
    # ever needs adjustment.
    exclusion {
      match_variable = "QueryStringArgNames"
      operator       = "Equals"
      selector       = "code"
    }

    exclusion {
      match_variable = "QueryStringArgNames"
      operator       = "Equals"
      selector       = "state"
    }

    exclusion {
      match_variable = "QueryStringArgNames"
      operator       = "Equals"
      selector       = "session_state"
    }

    exclusion {
      match_variable = "RequestCookieNames"
      operator       = "StartsWith"
      selector       = "authjs."
    }

    exclusion {
      match_variable = "RequestCookieNames"
      operator       = "StartsWith"
      selector       = "__Secure-authjs."
    }

    exclusion {
      match_variable = "RequestCookieNames"
      operator       = "StartsWith"
      selector       = "__Host-authjs."
    }
  }
}

resource "azurerm_cdn_frontdoor_route" "web" {
  name                          = local.frontdoor_route_name
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.platform.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.web.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.web.id]
  supported_protocols           = ["Http", "Https"]
  patterns_to_match             = ["/*"]
  forwarding_protocol           = "HttpsOnly"
  https_redirect_enabled        = true
  # Keep the azurefd.net endpoint routable even when a custom domain is bound.
  # This enables synthetic monitors/appliances to target the stable default hostname.
  link_to_default_domain          = true
  cdn_frontdoor_custom_domain_ids = local.use_custom_domain ? [azurerm_cdn_frontdoor_custom_domain.platform[0].id] : []
}

resource "azurerm_cdn_frontdoor_security_policy" "platform" {
  name                     = "${var.name_prefix}-afd-sec"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.platform.id

      association {
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.platform.id
        }

        dynamic "domain" {
          for_each = local.use_custom_domain ? [azurerm_cdn_frontdoor_custom_domain.platform[0].id] : []
          content {
            cdn_frontdoor_domain_id = domain.value
          }
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
