resource "azurerm_role_assignment" "storage_blob_data_contributor" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_role_assignment" "key_vault_secrets_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_container_app_environment_variable" "api_storage_account" {
  name             = "CNA_STORAGE_ACCOUNT_NAME"
  container_app_id = var.api_container_app_id
  value            = var.storage_account_name
}

resource "azurerm_container_app_environment_variable" "api_openai_endpoint" {
  name             = "CNA_AZURE_OPENAI_ENDPOINT"
  container_app_id = var.api_container_app_id
  value            = var.azure_openai_endpoint
}

resource "azurerm_container_app_environment_variable" "api_appinsights_connection" {
  name             = "APPLICATIONINSIGHTS_CONNECTION_STRING"
  container_app_id = var.api_container_app_id
  value            = var.application_insights_connection_string
}

resource "azurerm_container_app_environment_variable" "worker_storage_account" {
  name             = "CNA_STORAGE_ACCOUNT_NAME"
  container_app_id = var.worker_container_app_id
  value            = var.storage_account_name
}

resource "azurerm_container_app_environment_variable" "worker_openai_endpoint" {
  name             = "CNA_AZURE_OPENAI_ENDPOINT"
  container_app_id = var.worker_container_app_id
  value            = var.azure_openai_endpoint
}

resource "azurerm_container_app_environment_variable" "worker_appinsights_connection" {
  name             = "APPLICATIONINSIGHTS_CONNECTION_STRING"
  container_app_id = var.worker_container_app_id
  value            = var.application_insights_connection_string
}
