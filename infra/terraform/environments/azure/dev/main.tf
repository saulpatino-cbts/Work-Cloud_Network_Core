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
  tags                = local.tags
}

module "ai" {
  source              = "../../../providers/azure/ai"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  name_prefix         = local.name_prefix
  tags                = local.tags
}
