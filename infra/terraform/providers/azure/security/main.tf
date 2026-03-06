resource "azurerm_key_vault_secret" "openai_endpoint" {
  name         = "cna-azure-openai-endpoint"
  value        = var.azure_openai_endpoint
  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "appinsights_connection_string" {
  name         = "cna-applicationinsights-connection-string"
  value        = var.application_insights_connection_string
  key_vault_id = var.key_vault_id
}

resource "azurerm_role_assignment" "key_vault_secrets_officer" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_network_security_group" "platform" {
  name                = "nsg-${var.name_prefix}-platform"
  location            = var.location
  resource_group_name = var.resource_group_name
}

resource "azurerm_network_security_rule" "allow_api_ingress" {
  name                        = "allow-api-ingress"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefixes     = var.allowed_api_cidrs
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.platform.name
}

resource "azurerm_role_assignment" "api_managed_identity_acrpull" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.managed_identity_principal_id
}
