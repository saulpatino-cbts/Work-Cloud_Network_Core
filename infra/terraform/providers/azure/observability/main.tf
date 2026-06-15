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
