resource "azurerm_log_analytics_workspace" "compute" {
  name                = "law-${var.name_prefix}-platform"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_in_days
  tags                = var.tags
}

resource "azurerm_container_app_environment" "this" {
  name                           = local.container_apps_env_name
  location                       = var.location
  resource_group_name            = var.resource_group_name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.compute.id
  internal_load_balancer_enabled = var.container_apps_internal_only
  infrastructure_subnet_id       = var.infrastructure_subnet_id
  tags                           = var.tags
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

  registry {
    server   = var.container_registry_server
    identity = "system"
  }

  dynamic "secret" {
    for_each = var.container_app_secrets
    content {
      name  = secret.key
      value = secret.value
    }
  }

  template {
    min_replicas = var.container_app_min_replicas
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
    external_enabled = var.container_apps_internal_only ? false : true
    target_port      = var.api_target_port
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

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
    server   = var.container_registry_server
    identity = "system"
  }

  dynamic "secret" {
    for_each = var.container_app_secrets
    content {
      name  = secret.key
      value = secret.value
    }
  }

  template {
    min_replicas = 1
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
