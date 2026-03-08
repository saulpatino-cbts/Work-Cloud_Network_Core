resource "azurerm_cdn_profile" "this" {
  name                = local.cdn_profile_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "Standard_Microsoft"
  tags                = var.tags
}

resource "azurerm_cdn_endpoint" "this" {
  name                = local.cdn_endpoint_name
  profile_name        = azurerm_cdn_profile.this.name
  location            = var.location
  resource_group_name = var.resource_group_name
  is_http_allowed     = false
  is_https_allowed    = true
  origin_host_header  = "${var.storage_account_name}.z22.web.core.windows.net"

  origin {
    name      = "static-site-origin"
    host_name = "${var.storage_account_name}.z22.web.core.windows.net"
  }

  tags = var.tags
}
