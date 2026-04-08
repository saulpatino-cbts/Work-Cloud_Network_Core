data "azurerm_client_config" "current" {}

resource "azurerm_user_assigned_identity" "this" {
  name                = local.managed_identity_name
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}


resource "azurerm_key_vault" "this" {
  name                       = local.key_vault_name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = var.key_vault_soft_delete_retention_days
  purge_protection_enabled   = var.key_vault_purge_protection_enabled
  rbac_authorization_enabled = true
  tags                       = var.tags
}

resource "azurerm_role_assignment" "terraform_key_vault_officer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "time_sleep" "wait_for_rbac_propagation" {
  depends_on = [azurerm_role_assignment.terraform_key_vault_officer]

  create_duration = "60s"
}
