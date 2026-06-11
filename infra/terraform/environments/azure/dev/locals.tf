locals {
  org_name    = "cbts"
  name_prefix = "${local.org_name}-${var.project_name}-${var.environment}-${var.region_short}"
  tags = {
    Environment = title(var.environment)
    CostCenter  = "CBTS-CNA"
    Owner       = "cna-platform@cbts.com"
    Project     = var.project_name
    Org         = local.org_name
    ManagedBy   = "terraform"
  }
}
