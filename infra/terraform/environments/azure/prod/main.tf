resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}-platform"
  location = var.location
  tags     = local.tags
}
