resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}-platform"
  location = var.location
  tags     = local.tags
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
  source              = "../../../providers/azure/compute"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  api_image           = var.api_image
  worker_image        = var.worker_image
  tags                = local.tags
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
  worker_container_app_id                = module.compute.worker_id
  azure_openai_endpoint                  = module.ai.azure_openai_endpoint
  application_insights_connection_string = module.ai.application_insights_connection_string
}
