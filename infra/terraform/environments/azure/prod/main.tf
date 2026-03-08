resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}-platform"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "platform" {
  name                = "vnet-${local.name_prefix}-platform"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = ["10.50.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "container_apps_infra" {
  name                 = "snet-${local.name_prefix}-aca-infra"
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
  name                                           = "snet-${local.name_prefix}-private-endpoints"
  resource_group_name                            = azurerm_resource_group.this.name
  virtual_network_name                           = azurerm_virtual_network.platform.name
  address_prefixes                               = ["10.50.2.0/24"]
  private_endpoint_network_policies = "Disabled"
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
  container_apps_internal_only = true
  infrastructure_subnet_id     = azurerm_subnet.container_apps_infra.id
  tags                         = local.tags
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
  source                                 = "../../../providers/azure/runtime"
  resource_group_name                    = azurerm_resource_group.this.name
  storage_account_id                     = module.storage.storage_account_id
  storage_account_name                   = module.storage.storage_account_name
  key_vault_id                           = module.identity.key_vault_id
  managed_identity_principal_id          = module.identity.managed_identity_principal_id
  azure_openai_endpoint                  = module.ai.azure_openai_endpoint
  application_insights_connection_string = module.ai.application_insights_connection_string
  api_container_app_id                   = module.compute.api_id
  worker_container_app_id                = module.compute.worker_id
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
  worker_container_app_id                = module.compute.worker_id
  azure_openai_account_id                = module.ai.azure_openai_account_id
  azure_openai_endpoint                  = module.ai.azure_openai_endpoint
  application_insights_connection_string = module.ai.application_insights_connection_string
  virtual_network_id                     = azurerm_virtual_network.platform.id
  private_endpoint_subnet_id             = azurerm_subnet.private_endpoints.id
  storage_account_id                     = module.storage.storage_account_id
  storage_account_name                   = module.storage.storage_account_name
}
