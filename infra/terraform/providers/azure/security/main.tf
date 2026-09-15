locals {
  frontdoor_origin_name      = "${var.name_prefix}-afd-origin"
  frontdoor_route_name       = "${var.name_prefix}-afd-route"
  use_custom_domain          = var.frontdoor_custom_domain_host_name != ""
  use_custom_domain_dns_zone = local.use_custom_domain && var.frontdoor_custom_domain_dns_zone_id != null
  use_customer_managed_tls   = var.frontdoor_secret_versionless_id != null && var.frontdoor_certificate_type == "CustomerCertificate"

  # Private endpoints on Azure Container Apps only support inbound HTTP traffic
  # (https://learn.microsoft.com/azure/container-apps/how-to-integrate-with-azure-front-door#add-a-route).
  # "HttpsOnly" forwarding would break the origin the moment Private Link is
  # enabled, so let Front Door match whatever the client used instead of
  # forcing HTTPS to an origin that can't accept it over the private link.
  frontdoor_forwarding_protocol = var.frontdoor_private_link_enabled ? "MatchRequest" : "HttpsOnly"
}

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone" "keyvault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = var.resource_group_name
}

# PostgreSQL Flexible Server with VNet integration (delegated subnet).
# Azure registers the server via a hash-named A record in this zone
# (e.g. c2779f1c3041.privatelink.postgres.database.azure.com → private IP).
# The server FQDN's public CNAME points directly to that hash name, so the
# private zone resolves it correctly from within the VNet.
resource "azurerm_private_dns_zone" "postgres" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone" "cognitiveservices" {
  name                = "privatelink.cognitiveservices.azure.com"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone" "openai" {
  name                = "privatelink.openai.azure.com"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone" "services_ai" {
  name                = "privatelink.services.ai.azure.com"
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

resource "azurerm_private_dns_zone_virtual_network_link" "cognitiveservices" {
  name                  = "${var.name_prefix}-pdns-cog"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.cognitiveservices.name
  virtual_network_id    = var.virtual_network_id
}

resource "azurerm_private_dns_zone_virtual_network_link" "openai" {
  name                  = "${var.name_prefix}-pdns-oai"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.openai.name
  virtual_network_id    = var.virtual_network_id
}

resource "azurerm_private_dns_zone_virtual_network_link" "services_ai" {
  name                  = "${var.name_prefix}-pdns-sai"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.services_ai.name
  virtual_network_id    = var.virtual_network_id
}

# Private endpoints attach to resources (Cognitive Services/Foundry account,
# storage, Key Vault) created in other modules. Terraform's implicit dependency
# via the *_id inputs only guarantees the resource exists — not that it has
# reached a terminal provisioning state. Azure rejects a private-endpoint
# connection against a still-provisioning Cognitive Services account with
# "RequestConflict: provisioning state is not terminal". This delay lets the
# targets settle before any PE is created.
resource "time_sleep" "private_endpoint_settle" {
  create_duration = var.private_endpoint_settle_duration

  triggers = {
    # The empty-string substitute keeps the trigger byte-identical in saas mode
    # (join() rejects null elements), so introducing ai_mode does not replace
    # the sleep. Not coalesce(): it errors when every argument is null/empty.
    targets = join(",", [
      var.storage_account_id,
      var.key_vault_id,
      var.foundry_account_id != null ? var.foundry_account_id : "",
    ])
  }
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

  depends_on = [time_sleep.private_endpoint_settle]
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

  depends_on = [time_sleep.private_endpoint_settle]
}

# Present only when a Foundry account exists (workload ai_mode = saas). The
# cognitive/openai/services_ai private DNS zones above stay unconditional: they
# cost pennies and removing them would add churn for no functional gain.
resource "azurerm_private_endpoint" "foundry" {
  count               = var.foundry_account_id != null ? 1 : 0
  name                = "${var.name_prefix}-pep-aif"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "${var.name_prefix}-pep-psc-aif"
    private_connection_resource_id = var.foundry_account_id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name = "pdzg-cognitiveservices"
    private_dns_zone_ids = [
      azurerm_private_dns_zone.cognitiveservices.id,
      azurerm_private_dns_zone.openai.id,
      azurerm_private_dns_zone.services_ai.id
    ]
  }

  depends_on = [time_sleep.private_endpoint_settle]
}

# Adding count re-addresses the live private endpoint; without this the plan
# destroys and recreates it. Module-relative address applies to every instance
# of this module. Safe to delete once every environment has applied.
moved {
  from = azurerm_private_endpoint.foundry
  to   = azurerm_private_endpoint.foundry[0]
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
      key_vault_certificate_id = var.frontdoor_certificate_pfx_path != null ? azurerm_key_vault_certificate.frontdoor[0].versionless_secret_id : var.frontdoor_secret_versionless_id
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

  dynamic "private_link" {
    for_each = var.frontdoor_private_link_enabled ? [1] : []
    content {
      location               = var.location
      private_link_target_id = var.container_app_environment_id
      request_message        = var.frontdoor_private_link_request_message
      target_type            = var.frontdoor_private_link_target_type
    }
  }
}

resource "azurerm_cdn_frontdoor_custom_domain" "platform" {
  count                    = local.use_custom_domain ? 1 : 0
  name                     = "${var.name_prefix}-afd-domain"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
  dns_zone_id              = local.use_custom_domain_dns_zone ? var.frontdoor_custom_domain_dns_zone_id : null
  host_name                = var.frontdoor_custom_domain_host_name

  tls {
    certificate_type        = var.frontdoor_certificate_type
    minimum_version         = var.frontdoor_minimum_tls_version
    cdn_frontdoor_secret_id = local.use_customer_managed_tls ? azurerm_cdn_frontdoor_secret.platform[0].id : null
  }
}

resource "azurerm_cdn_frontdoor_firewall_policy" "platform" {
  # Azure requires WAF policy names to be alphanumeric only — no hyphens allowed.
  name                = "${replace(var.name_prefix, "-", "")}fdfp"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"

  # Signed off per GitHub issue #111 — the narrow, field-specific exclusion
  # set below (rather than a blanket path-based Allow) is the approved
  # mitigation for the two known Auth.js/DefaultRuleSet 1.0 false-positive
  # sources on the sign-in path. var.frontdoor_waf_mode defaults to
  # "Prevention"; keep monitoring FrontDoorWebApplicationFirewallLog for any
  # Block on /auth/* or /api/auth/* after each deploy.
  mode = var.frontdoor_waf_mode

  # Auth.js v5 Server Actions POST to /auth/signin with a Next-Action header
  # and text/plain body — both of which trigger OWASP anomaly scoring rules in
  # DefaultRuleSet 1.0. The OAuth callback arrives at /api/auth/callback/* with
  # long JWT-like ?code= and ?state= params that trigger SQLI rules.
  #
  # A prior version of this policy used a blanket "Allow" custom rule on all
  # of /auth/* and /api/auth/*, which terminated WAF evaluation for the entire
  # authentication surface — no OWASP inspection at all on a high-value attack
  # target. That has been removed in favor of the narrow, field-specific
  # exclusions below, which only exempt the exact params/cookies/headers known
  # to false-positive and leave every other part of the request (other query
  # args, other headers) fully inspected by the managed rule set.
  #
  # KNOWN GAP: per Microsoft Learn (learn.microsoft.com/azure/web-application-
  # firewall/afds/waf-front-door-exclusion#body-contents-inspection), the raw
  # text/plain Server Action body itself cannot be excluded via an exclusion
  # list — unparsed body content surfaces in WAF logs as InitialBodyContents /
  # DecodedInitialBodyContents, which exclusions don't support. Signed off in
  # issue #111 as an accepted residual risk covered by log monitoring: if the
  # sign-in POST body ever trips a rule in Prevention mode, the fix is a
  # narrowly-scoped managed_rule.override on the specific rule_id that fires —
  # not a reintroduction of the broad path-based Allow rule.
  managed_rule {
    type    = "DefaultRuleSet"
    version = "1.0"
    action  = "Block"

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

    # Next.js Server Actions marker header — Auth.js v5's /auth/signin POST
    # sends this, and its value has tripped anomaly-scoring rules in testing.
    exclusion {
      match_variable = "RequestHeaderNames"
      operator       = "Equals"
      selector       = "Next-Action"
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
  forwarding_protocol           = local.frontdoor_forwarding_protocol
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

resource "azurerm_key_vault_certificate" "frontdoor" {
  count        = var.frontdoor_certificate_pfx_path != null ? 1 : 0
  name         = "afd-cert"
  key_vault_id = var.key_vault_id

  certificate {
    contents = filebase64(var.frontdoor_certificate_pfx_path)
    password = var.frontdoor_certificate_pfx_password
  }

  certificate_policy {
    issuer_parameters {
      name = "Unknown"
    }
    key_properties {
      exportable = true
      key_size   = 2048
      key_type   = "RSA"
      reuse_key  = true
    }
    secret_properties {
      content_type = "application/x-pkcs12"
    }
  }
}
