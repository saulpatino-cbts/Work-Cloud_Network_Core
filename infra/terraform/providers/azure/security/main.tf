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
