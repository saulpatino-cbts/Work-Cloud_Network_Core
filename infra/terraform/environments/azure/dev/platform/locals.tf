locals {
  name_prefix = "${var.project_name}-${var.environment}-${var.region_short}"
  tags = {
    Environment = title(var.environment)
    CostCenter  = "CNA"
    Owner       = "cna-platform"
    Project     = var.project_name
    ManagedBy   = "terraform"
  }

  firewall_application_rule_fqdns = [
    "index.docker.io",
    "registry-1.docker.io",
    "auth.docker.io",
    "production.cloudfront.docker.com",
    "pkg-containers.githubusercontent.com",
    "login.microsoftonline.com",
    "management.azure.com",
    "dc.applicationinsights.azure.com",
    "live.applicationinsights.azure.com",
    "*.in.applicationinsights.azure.com",
    "*.livediagnostics.monitor.azure.com",
  ]
}
