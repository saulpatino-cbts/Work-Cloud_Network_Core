locals {
  app_insights_name = "appi-${var.name_prefix}-platform"
  foundry_tags = {
    component = "foundry"
    region    = "eus2"
  }
}
