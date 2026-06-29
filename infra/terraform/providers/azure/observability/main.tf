data "azurerm_monitor_diagnostic_categories" "target" {
  for_each    = var.diagnostic_targets
  resource_id = each.value
}

locals {
  diagnostic_targets = {
    for name, resource_id in var.diagnostic_targets : name => {
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
