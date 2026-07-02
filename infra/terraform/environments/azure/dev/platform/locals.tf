locals {
  name_prefix = "${var.project_name}-${var.environment}-${var.region_short}"
  tags = {
    Environment = title(var.environment)
    CostCenter  = "CNA"
    Owner       = "cna-platform"
    Project     = var.project_name
    ManagedBy   = "terraform"
  }

  # Log Analytics retention (days). 30 is the PerGB2018 SKU floor.
  log_analytics_retention_in_days = 30

  firewall_application_rule_fqdns = [
    "index.docker.io",
    "registry-1.docker.io",
    "auth.docker.io",
    "production.cloudfront.docker.com",
    "pkg-containers.githubusercontent.com",
    "login.microsoftonline.com",
    # Regional Entra ID (ESTS-R) endpoints: the Container Apps managed-identity
    # sidecar fetches tokens from <region>.login.microsoft.com, NOT the classic
    # login.microsoftonline.com. Without this, every managed-identity token
    # request in the environment fails with an opaque 500 ("An unexpected error
    # occured while fetching the AAD Token") — which breaks Key Vault references,
    # Storage, and all AI calls. Diagnosed 2026-07-02 from AZFW deny logs.
    "*.login.microsoft.com",
    "login.microsoft.com",
    # Container Apps managed-environment required FQDN (node package updates);
    # also seen denied in AZFW logs.
    "packages.aks.azure.com",
    # Microsoft Container Registry — ACA infrastructure images.
    "mcr.microsoft.com",
    "*.data.mcr.microsoft.com",
    "management.azure.com",
  ]
}
