locals {
  name_prefix = "${var.project_name}-${var.environment}-${var.region_short}"
  tags = {
    project     = var.project_name
    environment = var.environment
    region      = var.region_short
    managed_by  = "terraform"
    platform    = "cna"
  }
}
