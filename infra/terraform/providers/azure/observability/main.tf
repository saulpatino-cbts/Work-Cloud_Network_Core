locals {
  # On an Azure Landing Zone, a "deploy diagnostic settings at scale" initiative
  # (DeployIfNotExists, e.g. Deploy-Diag-Logs) assigned at a management-group
  # scope auto-creates a "setByPolicy-*" diagnostic setting on every resource the
  # moment it is created. Azure permits up to FIVE diagnostic settings per
  # resource, so our uniquely-named setting and the policy's setting coexist
  # (dual-ship: logs land in BOTH our local workspace and the central one).
  #
  # The hazard is timing, not naming: the policy's DINE remediation writes a
  # diagnostic setting on the firewall concurrently with our apply, and the
  # azurerm provider's create-time existence pre-check can misfire during that
  # window ("already exists / needs import"). We serialize our settings behind a
  # short stabilization delay (see time_sleep below) so they are created after
  # the target resources provision and the policy remediation settles.
  #
  # var.manage_diagnostic_settings remains a safety valve: set it false to stand
  # down entirely (policy-only diagnostics) if an environment ever needs that.
  managed_diagnostic_targets = var.manage_diagnostic_settings ? var.diagnostic_targets : {}
}

data "azurerm_monitor_diagnostic_categories" "target" {
  for_each    = local.managed_diagnostic_targets
  resource_id = each.value
}

# Stabilization delay: lets the target resources finish provisioning and any ALZ
# DeployIfNotExists diagnostic-settings remediation settle before we create our
# own (uniquely named) settings, eliminating the azurerm create-race false
# "already exists" error on policy-governed subscriptions.
resource "time_sleep" "diagnostic_settle" {
  count           = length(local.managed_diagnostic_targets) > 0 ? 1 : 0
  create_duration = var.diagnostic_settings_settle_duration

  triggers = {
    targets = join(",", values(local.managed_diagnostic_targets))
  }
}

locals {
  diagnostic_targets = {
    for name, resource_id in local.managed_diagnostic_targets : name => {
      resource_id         = resource_id
      log_category_groups = data.azurerm_monitor_diagnostic_categories.target[name].log_category_groups
      log_category_types  = data.azurerm_monitor_diagnostic_categories.target[name].log_category_types
      metric_categories   = data.azurerm_monitor_diagnostic_categories.target[name].metrics
    }
  }
}

resource "azurerm_monitor_diagnostic_setting" "target" {
  for_each = local.diagnostic_targets

  name                       = substr("${var.diagnostic_setting_name_prefix}-${replace(each.key, "_", "-")}", 0, 63)
  target_resource_id         = each.value.resource_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  depends_on = [time_sleep.diagnostic_settle]

  dynamic "enabled_log" {
    for_each = length(each.value.log_category_groups) > 0 ? each.value.log_category_groups : []
    content {
      category_group = enabled_log.value
    }
  }

  dynamic "enabled_log" {
    for_each = length(each.value.log_category_groups) == 0 ? each.value.log_category_types : []
    content {
      category = enabled_log.value
    }
  }

  dynamic "enabled_metric" {
    for_each = each.value.metric_categories
    content {
      category = enabled_metric.value
    }
  }
}

# Azure auto-provisions exactly one Network Watcher per region per subscription
# (named NetworkWatcher_<region> in the NetworkWatcherRG resource group) and
# enforces a hard limit of one. Creating or updating a virtual network triggers
# this automatic enablement. Managing our own instance collides with that
# singleton ("NetworkWatcherCountLimitReached"), so we reference the existing one
# instead of creating it. The flow log is parented to this pre-existing watcher.
data "azurerm_network_watcher" "this" {
  count = var.enable_virtual_network_flow_logs ? 1 : 0

  name                = "NetworkWatcher_${replace(lower(var.location), " ", "")}"
  resource_group_name = "NetworkWatcherRG"
}

resource "azapi_resource" "virtual_network_flow_log" {
  count = var.enable_virtual_network_flow_logs ? 1 : 0

  type      = "Microsoft.Network/networkWatchers/flowLogs@2025-05-01"
  name      = "${var.diagnostic_setting_name_prefix}-vnet-flow"
  parent_id = data.azurerm_network_watcher.this[0].id
  location  = var.location
  tags      = var.tags

  body = {
    properties = {
      enabled     = true
      recordTypes = "B,C,E,D"
      format = {
        type    = "JSON"
        version = 2
      }
      retentionPolicy = {
        enabled = true
        days    = var.flow_log_retention_days
      }
      storageId        = var.flow_log_storage_account_id
      targetResourceId = var.flow_log_target_resource_id
      flowAnalyticsConfiguration = {
        networkWatcherFlowAnalyticsConfiguration = {
          enabled                  = true
          trafficAnalyticsInterval = var.flow_log_traffic_analytics_interval
          workspaceId              = var.log_analytics_workspace_workspace_id
          workspaceRegion          = var.log_analytics_workspace_location
          workspaceResourceId      = var.log_analytics_workspace_id
        }
      }
    }
  }
}
