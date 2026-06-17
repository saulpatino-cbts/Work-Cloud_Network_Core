resource "azurerm_log_analytics_workspace" "compute" {
  name                = "${var.name_prefix}-log"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_in_days
  tags                = var.tags
}

resource "azurerm_container_app_environment" "this" {
  name                               = local.container_apps_env_name
  location                           = var.location
  resource_group_name                = var.resource_group_name
  log_analytics_workspace_id         = azurerm_log_analytics_workspace.compute.id
  internal_load_balancer_enabled     = var.container_apps_internal_only
  public_network_access              = var.container_apps_public_network_access
  infrastructure_subnet_id           = var.infrastructure_subnet_id
  infrastructure_resource_group_name = local.container_apps_infra_resource_group_name
  tags                               = var.tags

  dynamic "workload_profile" {
    for_each = var.container_app_environment_workload_profiles
    content {
      name                  = workload_profile.value.name
      workload_profile_type = workload_profile.value.workload_profile_type
      minimum_count         = try(workload_profile.value.minimum_count, null)
      maximum_count         = try(workload_profile.value.maximum_count, null)
    }
  }
}

resource "azurerm_container_app" "api" {
  name                         = local.api_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = var.container_app_revision_mode
  tags                         = var.tags

  identity {
    type = "SystemAssigned"
  }

  # GHCR requires username + PAT — Azure Managed Identity only works with ACR.
  registry {
    server               = var.container_registry_server
    username             = local.use_ghcr_auth ? var.ghcr_username : null
    password_secret_name = local.use_ghcr_auth ? "ghcr-pat" : null
    identity             = local.use_ghcr_auth ? null : "system"
  }

  # Inject the GHCR PAT as a secret so the registry block can reference it.
  dynamic "secret" {
    for_each = local.use_ghcr_auth ? [{ name = "ghcr-pat" }] : []
    content {
      name  = secret.value.name
      value = var.ghcr_pat
    }
  }

  dynamic "secret" {
    for_each = [for name in nonsensitive(keys(var.container_app_secrets)) : { name = name }]
    content {
      name  = secret.value.name
      value = var.container_app_secrets[secret.value.name]
    }
  }

  template {
    # FinOps: scale_to_zero overrides min_replicas to 0 for dev environments.
    # When idle, Container Apps cost $0. Cold-start is ~5-10s.
    min_replicas = var.enable_scale_to_zero ? 0 : var.container_app_min_replicas
    max_replicas = var.container_app_max_replicas

    container {
      name   = "cna-api"
      image  = var.api_image
      cpu    = 0.5
      memory = "1Gi"

      liveness_probe {
        transport = "HTTP"
        port      = var.api_target_port
        path      = "/health"
      }

      readiness_probe {
        transport = "HTTP"
        port      = var.api_target_port
        path      = "/health"
      }

      startup_probe {
        transport = "HTTP"
        port      = var.api_target_port
        path      = "/health"
      }

      dynamic "env" {
        for_each = local.api_plain_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      dynamic "env" {
        for_each = local.api_secret_env_vars
        content {
          name        = env.value.name
          secret_name = env.value.secret_name
        }
      }
    }
  }

  ingress {
    external_enabled = false # Internal only — Front Door routes to cna-web, not cna-api
    target_port      = var.api_target_port
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# ─── cna-worker ───────────────────────────────────────────────────────────────
# Background job processor. No HTTP ingress — processes discovery, analysis,
# and delivery pipelines asynchronously.
resource "azurerm_container_app" "worker" {
  name                         = local.worker_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = var.container_app_revision_mode
  tags                         = var.tags

  identity {
    type = "SystemAssigned"
  }

  registry {
    server               = var.container_registry_server
    username             = local.use_ghcr_auth ? var.ghcr_username : null
    password_secret_name = local.use_ghcr_auth ? "ghcr-pat" : null
    identity             = local.use_ghcr_auth ? null : "system"
  }

  dynamic "secret" {
    for_each = local.use_ghcr_auth ? [{ name = "ghcr-pat" }] : []
    content {
      name  = secret.value.name
      value = var.ghcr_pat
    }
  }

  dynamic "secret" {
    for_each = [for name in nonsensitive(keys(var.container_app_secrets)) : { name = name }]
    content {
      name  = secret.value.name
      value = var.container_app_secrets[secret.value.name]
    }
  }

  template {
    min_replicas = var.enable_scale_to_zero ? 0 : var.container_app_min_replicas
    max_replicas = var.container_app_max_replicas

    container {
      name   = "cna-worker"
      image  = var.worker_image
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.worker_plain_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      dynamic "env" {
        for_each = local.worker_secret_env_vars
        content {
          name        = env.value.name
          secret_name = env.value.secret_name
        }
      }
    }
  }
}

# ─── cna-web ──────────────────────────────────────────────────────────────────
# Next.js frontend + API routes. Public face of the CNA platform.
# Azure Front Door terminates TLS and WAF here. Port 3000.
resource "azurerm_container_app" "web" {
  name                         = local.web_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = var.container_app_revision_mode
  tags                         = var.tags

  identity {
    type = "SystemAssigned"
  }

  registry {
    server               = var.container_registry_server
    username             = local.use_ghcr_auth ? var.ghcr_username : null
    password_secret_name = local.use_ghcr_auth ? "ghcr-pat" : null
    identity             = local.use_ghcr_auth ? null : "system"
  }

  dynamic "secret" {
    for_each = local.use_ghcr_auth ? [{ name = "ghcr-pat" }] : []
    content {
      name  = secret.value.name
      value = var.ghcr_pat
    }
  }

  dynamic "secret" {
    for_each = [for name in nonsensitive(keys(var.container_app_secrets)) : { name = name }]
    content {
      name  = secret.value.name
      value = var.container_app_secrets[secret.value.name]
    }
  }

  template {
    min_replicas = var.enable_scale_to_zero ? 0 : var.container_app_min_replicas
    max_replicas = var.container_app_max_replicas

    container {
      name   = "cna-web"
      image  = var.web_image
      cpu    = 0.5
      memory = "1Gi"

      liveness_probe {
        transport = "HTTP"
        port      = var.web_target_port
        path      = "/api/health"
      }

      readiness_probe {
        transport = "HTTP"
        port      = var.web_target_port
        path      = "/api/health"
      }

      startup_probe {
        transport = "HTTP"
        port      = var.web_target_port
        path      = "/api/health"
      }

      dynamic "env" {
        for_each = local.web_plain_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      dynamic "env" {
        for_each = local.web_secret_env_vars
        content {
          name        = env.value.name
          secret_name = env.value.secret_name
        }
      }
    }
  }

  ingress {
    external_enabled = true # Public — Azure Front Door terminates TLS here
    target_port      = var.web_target_port
    transport        = "auto"

    # Phase 1 groundwork: support origin hardening without redesigning the
    # compute module. AzureRM currently supports CIDR-based restrictions here,
    # which is enough to introduce controlled ingress rules when the final
    # Front Door origin pattern is selected.
    dynamic "ip_security_restriction" {
      for_each = var.web_ingress_ip_security_restrictions
      content {
        name             = ip_security_restriction.value.name
        action           = ip_security_restriction.value.action
        ip_address_range = ip_security_restriction.value.ip_address_range
        description      = try(ip_security_restriction.value.description, null)
      }
    }

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}
