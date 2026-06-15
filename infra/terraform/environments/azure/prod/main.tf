# Workload resource group — created by workflow 000 and immediately imported
# into Terraform state so 031 / 032 continue to own the full app stack RG.
resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "platform" {
  name                = "${local.name_prefix}-vnet"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = ["10.50.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "container_apps_infra" {
  name                 = "${local.name_prefix}-snet-aca"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = ["10.50.0.0/23"]

  delegation {
    name = "container-apps-delegation"

    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action"
      ]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "${local.name_prefix}-snet-pe"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.platform.name
  address_prefixes                  = ["10.50.2.0/24"]
  private_endpoint_network_policies = "Disabled"
}

# PostgreSQL Flexible Server requires a dedicated delegated subnet — it does NOT
# use a private endpoint. The subnet must be delegated to
# Microsoft.DBforPostgreSQL/flexibleServers and cannot contain other resources.
resource "azurerm_subnet" "database" {
  name                 = "${local.name_prefix}-snet-db"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = ["10.50.3.0/24"]

  delegation {
    name = "postgres-flexible-delegation"

    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action"
      ]
    }
  }
}

module "storage" {
  source              = "../../../providers/azure/storage"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  tags                = local.tags

  # Strict durability: GZRS provides zone and geo redundancy.
  replication_type            = "GZRS"
  raw_artifact_retention_days = 30 # move to Cool after 30 days
  deliverable_retention_days  = 90
}

module "identity" {
  source              = "../../../providers/azure/identity"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  tenant_id           = var.tenant_id
  tags                = local.tags

  # Zero Trust: purge protection prevents accidental permanent deletion of secrets
  # Note: once enabled, purge protection CANNOT be disabled without Microsoft support.
  key_vault_soft_delete_retention_days = 90
  key_vault_purge_protection_enabled   = true
}

module "compute" {
  source                               = "../../../providers/azure/compute"
  resource_group_name                  = azurerm_resource_group.this.name
  location                             = azurerm_resource_group.this.location
  name_prefix                          = local.name_prefix
  api_image                            = var.api_image
  worker_image                         = var.worker_image
  web_image                            = var.web_image
  container_apps_internal_only         = false
  container_apps_public_network_access = "Disabled"
  container_app_environment_workload_profiles = [{
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }]
  infrastructure_subnet_id             = azurerm_subnet.container_apps_infra.id
  web_ingress_ip_security_restrictions = var.web_ingress_ip_security_restrictions
  ghcr_username                        = var.ghcr_username
  ghcr_pat                             = var.ghcr_pat
  tags                                 = local.tags

  # FinOps: do NOT scale to zero in prod — cold-start impacts SLA
  enable_scale_to_zero            = false
  log_analytics_retention_in_days = 90 # Compliance: 90 days for prod

  # ── Plain env vars injected at container start ─────────────────────────────
  api_env_vars = {
    CNA_STORAGE_ACCOUNT_NAME              = module.storage.storage_account_name
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.ai.application_insights_connection_string
  }

  worker_env_vars = {
    CNA_STORAGE_ACCOUNT_NAME              = module.storage.storage_account_name
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.ai.application_insights_connection_string
  }

  web_env_vars = {
    NEXTAUTH_URL                          = var.nextauth_url
    AUTH_TRUST_HOST                       = "true"
    AZURE_AD_TENANT_ID                    = var.tenant_id
    AZURE_AD_CLIENT_ID                    = var.entra_client_id
    CNA_API_INTERNAL_URL                  = "http://${local.name_prefix}-ca-api"
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.ai.application_insights_connection_string
    AZURE_STORAGE_ACCOUNT_NAME            = module.storage.storage_account_name
    AZURE_STORAGE_CONTAINER_ENGAGEMENTS   = "raw-artifacts"
    CNA_AI_ENGINE_DEFAULT                 = var.ai_engine_default
    FOUNDRY_CLAUDE_ENDPOINT               = var.foundry_claude_endpoint != "" ? var.foundry_claude_endpoint : module.ai.foundry_claude_messages_endpoint
    FOUNDRY_CLAUDE_MODEL                  = var.foundry_claude_model
    CNA_AZURE_MCP_ENDPOINT                = var.azure_mcp_endpoint
    CNA_AZURE_MCP_TRANSPORT               = var.azure_mcp_transport
    CNA_AWS_MCP_ENDPOINT                  = var.aws_mcp_endpoint
    CNA_AWS_MCP_TRANSPORT                 = var.aws_mcp_transport
    CNA_DRAWIO_MCP_URL                    = var.drawio_mcp_url
  }

  # Secret-backed env vars — reference Container App secrets by name
  web_secret_env_vars = {
    DATABASE_URL              = "database-url"
    AUTH_SECRET               = "nextauth-secret" # Auth.js v5 canonical name (was NEXTAUTH_SECRET)
    AZURE_AD_CLIENT_SECRET    = "entra-client-secret"
    CREDENTIAL_ENCRYPTION_KEY = "credential-encryption-key"
    FOUNDRY_CLAUDE_API_KEY    = "foundry-claude-api-key"
  }

  # Container App secrets — encrypted values stored within the Container App.
  # These are the same secrets stored in Key Vault by the runtime module.
  # The runtime module persists them in KV for the 05-sync-env workflow;
  # these direct injections ensure the Container App can start before KV sync runs.
  container_app_secrets = {
    "database-url"              = module.database.connection_string
    "nextauth-secret"           = var.nextauth_secret
    "entra-client-secret"       = var.entra_client_secret
    "credential-encryption-key" = var.credential_encryption_key
    "foundry-claude-api-key"    = var.foundry_claude_api_key
  }
}

module "ai" {
  source              = "../../../providers/azure/ai"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  tags                = local.tags

  environment          = var.environment
  foundry_location     = "eastus2"
  foundry_account_name = "cna-prod-eus2-aif"
  foundry_project_name = "cna-prod-eus2-aif-proj"
}


# ─── Database ─────────────────────────────────────────────────────────────────
# PostgreSQL Flexible Server with VNet delegation (not private endpoint).
# The postgres private DNS zone is created in the security module and its ID
# is passed here. The server itself must be created AFTER the DNS zone + link.
module "database" {
  source                       = "../../../providers/azure/database"
  resource_group_name          = azurerm_resource_group.this.name
  location                     = azurerm_resource_group.this.location
  name_prefix                  = local.name_prefix
  db_subnet_id                 = azurerm_subnet.database.id
  postgres_private_dns_zone_id = module.security.postgres_private_dns_zone_id
  admin_username               = var.postgres_admin_username
  admin_password               = var.postgres_admin_password
  tags                         = local.tags

  # Prod-grade database: GP SKU, more storage, longer backup, geo-redundant
  sku_name                     = "GP_Standard_D2s_v3" # 2 vCores, 8GB RAM
  storage_mb                   = 65536                # 64GB — room for growth
  backup_retention_days        = 30                   # FinOps + compliance minimum
  geo_redundant_backup_enabled = true                 # Zero Trust: survive regional failure
}

module "runtime" {
  source                        = "../../../providers/azure/runtime"
  resource_group_name           = azurerm_resource_group.this.name
  storage_account_id            = module.storage.storage_account_id
  key_vault_id                  = module.identity.key_vault_id
  managed_identity_principal_id = module.identity.managed_identity_principal_id
  database_url                  = module.database.connection_string
  nextauth_secret               = var.nextauth_secret
  entra_client_secret           = var.entra_client_secret
}

module "security" {
  source                                 = "../../../providers/azure/security"
  resource_group_name                    = azurerm_resource_group.this.name
  location                               = azurerm_resource_group.this.location
  name_prefix                            = local.name_prefix
  key_vault_id                           = module.identity.key_vault_id
  key_vault_name                         = module.identity.key_vault_name
  managed_identity_principal_id          = module.identity.managed_identity_principal_id
  managed_identity_id                    = module.identity.managed_identity_id
  managed_identity_client_id             = module.identity.managed_identity_client_id
  api_container_app_id                   = module.compute.api_id
  api_container_app_fqdn                 = module.compute.api_fqdn
  web_container_app_id                   = module.compute.web_id
  web_container_app_fqdn                 = module.compute.web_fqdn
  container_app_environment_id           = module.compute.container_app_environment_id
  worker_container_app_id                = module.compute.worker_id
  application_insights_connection_string = module.ai.application_insights_connection_string
  frontdoor_private_link_enabled         = true
  virtual_network_id                     = azurerm_virtual_network.platform.id
  private_endpoint_subnet_id             = azurerm_subnet.private_endpoints.id
  storage_account_id                     = module.storage.storage_account_id
  storage_account_name                   = module.storage.storage_account_name
}

module "observability" {
  source                         = "../../../providers/azure/observability"
  log_analytics_workspace_id     = module.compute.log_analytics_workspace_id
  diagnostic_setting_name_prefix = local.name_prefix

  diagnostic_targets = {
    frontdoor_profile          = module.security.frontdoor_profile_id
    frontdoor_firewall_policy  = module.security.frontdoor_firewall_policy_id
    platform_nsg               = module.security.network_security_group_id
    container_apps_environment = module.compute.container_app_environment_id
    container_app_web          = module.compute.web_id
    container_app_api          = module.compute.api_id
    container_app_worker       = module.compute.worker_id
    key_vault                  = module.identity.key_vault_id
    storage_account            = module.storage.storage_account_id
    postgres_server            = module.database.server_id
    app_insights               = module.ai.application_insights_id
    foundry_account            = module.ai.foundry_account_id
  }
}

resource "azurerm_subnet_network_security_group_association" "container_apps_infra" {
  subnet_id                 = azurerm_subnet.container_apps_infra.id
  network_security_group_id = module.security.network_security_group_id
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  subnet_id                 = azurerm_subnet.private_endpoints.id
  network_security_group_id = module.security.network_security_group_id
}

resource "azurerm_subnet_network_security_group_association" "database" {
  subnet_id                 = azurerm_subnet.database.id
  network_security_group_id = module.security.network_security_group_id
}

# ─── Container App RBAC ───────────────────────────────────────────────────────
# Each Container App uses its system-assigned managed identity via
# DefaultAzureCredential. All required role assignments are declared here so
# Terraform owns the full identity surface — no manual az role assignment calls.

# Storage: web uploads deliverables; api + worker read/write raw artifacts.
resource "azurerm_role_assignment" "web_storage_blob_data_contributor" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.compute.web_principal_id
}

resource "azurerm_role_assignment" "api_storage_blob_data_contributor" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.compute.api_principal_id
}

resource "azurerm_role_assignment" "worker_storage_blob_data_contributor" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.compute.worker_principal_id
}
