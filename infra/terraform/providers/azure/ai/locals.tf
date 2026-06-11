locals {
  app_insights_name = "${var.name_prefix}-appi"
  foundry_tags = {
    component = "foundry"
    region    = "eus2"
  }
}
