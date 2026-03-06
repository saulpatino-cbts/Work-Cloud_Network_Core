locals {
  cognitive_account_name = substr(replace(lower("aoai-${var.name_prefix}"), "-", ""), 0, 24)
  app_insights_name      = "appi-${var.name_prefix}-platform"
}
