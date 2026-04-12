locals {
  cognitive_account_name = substr(replace(lower("aoai-${var.name_prefix}"), "-", ""), 0, 24)
  app_insights_name      = "appi-${var.name_prefix}-platform"
  # Use override location when set (e.g. eastus2 for gpt-5.x); fall back to workload location.
  openai_location = var.openai_location != "" ? var.openai_location : var.location
}
