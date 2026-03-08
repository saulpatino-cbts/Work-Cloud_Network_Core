# Workload resource group — created and managed by Terraform.
# Terraform state lives in a separate dedicated RG (rg-cna-tfstate) created
# by workflow 01, so this RG can be safely destroyed without affecting state.
resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "platform" {
  name                = "vnet-${local.name_prefix}-platform"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = ["10.40.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "container_apps_infra" {
  name                 = "snet-${local.name_prefix}-aca-infra"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = ["10.40.0.0/23"]

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
  name                              = "snet-${local.name_prefix}-private-endpoints"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.platform.name
  address_prefixes                  = ["10.40.2.0/24"]
  private_endpoint_network_policies = "Disabled"
}

# PostgreSQL Flexible Server requires a dedicated delegated subnet — it does NOT
# use a private endpoint. The subnet must be delegated to
# Microsoft.DBforPostgreSQL/flexibleServers and cannot contain other resources.
resource "azurerm_subnet" "database" {
  name                 = "snet-${local.name_prefix}-database"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = ["10.40.3.0/24"]

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
}

module "identity" {
  source              = "../../../providers/azure/identity"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  tenant_id           = var.tenant_id
  tags                = local.tags
}

module "compute" {
  source                       = "../../../providers/azure/compute"
  resource_group_name          = azurerm_resource_group.this.name
  location                     = azurerm_resource_group.this.location
  name_prefix                  = local.name_prefix
  api_image                    = var.api_image
  worker_image                 = var.worker_image
  web_image                    = var.web_image
  container_apps_internal_only = false # false = external LB so cna-web can serve public traffic
  infrastructure_subnet_id     = azurerm_subnet.container_apps_infra.id
  ghcr_username                = var.ghcr_username
  ghcr_pat                     = var.ghcr_pat
  tags                         = local.tags

  # ── Plain env vars injected at container start ──────────────────────────────
  api_env_vars = {
    CNA_STORAGE_ACCOUNT_NAME              = module.storage.storage_account_name
    CNA_AZURE_OPENAI_ENDPOINT             = module.ai.azure_openai_endpoint
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.ai.application_insights_connection_string
  }

  worker_env_vars = {
    CNA_STORAGE_ACCOUNT_NAME              = module.storage.storage_account_name
    CNA_AZURE_OPENAI_ENDPOINT             = module.ai.azure_openai_endpoint
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.ai.application_insights_connection_string
  }

  web_env_vars = {
    NEXTAUTH_URL                          = var.nextauth_url
    AZURE_AD_TENANT_ID                    = var.tenant_id
    AZURE_AD_CLIENT_ID                    = var.entra_client_id
    CNA_API_INTERNAL_URL                  = "http://ca-${local.name_prefix}-api"
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.ai.application_insights_connection_string
  }

  # ── Secret-backed env vars (reference Container App secrets by name) ─────────
  web_secret_env_vars = {
    DATABASE_URL         = "database-url"
    NEXTAUTH_SECRET      = "nextauth-secret"
    AZURE_AD_CLIENT_SECRET = "entra-client-secret"
  }

  # ── Container App secrets (encrypted values stored within Container Apps) ────
  # These are referenced by the web_secret_env_vars above. The actual values
  # come from Terraform variables set via GitHub Secrets in CI.
  container_app_secrets = {
    "database-url"      = module.database.connection_string
    "nextauth-secret"   = var.nextauth_secret
    "entra-client-secret" = var.entra_client_secret
  }
}

module "ai" {
  source              = "../../../providers/azure/ai"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  tags                = local.tags
}

module "presentation" {
  source               = "../../../providers/azure/presentation"
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  name_prefix          = local.name_prefix
  storage_account_id   = module.storage.storage_account_id
  storage_account_name = module.storage.storage_account_name
  tags                 = local.tags
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
  worker_container_app_id                = module.compute.worker_id
  azure_openai_account_id                = module.ai.azure_openai_account_id
  azure_openai_endpoint                  = module.ai.azure_openai_endpoint
  application_insights_connection_string = module.ai.application_insights_connection_string
  virtual_network_id                     = azurerm_virtual_network.platform.id
  private_endpoint_subnet_id             = azurerm_subnet.private_endpoints.id
  storage_account_id                     = module.storage.storage_account_id
  storage_account_name                   = module.storage.storage_account_name
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
}
