output "managed_identity_id" {
  value      = azurerm_user_assigned_identity.this.id
  depends_on = [time_sleep.wait_for_rbac_propagation]
}

output "managed_identity_client_id" {
  value      = azurerm_user_assigned_identity.this.client_id
  depends_on = [time_sleep.wait_for_rbac_propagation]
}

output "managed_identity_principal_id" {
  value      = azurerm_user_assigned_identity.this.principal_id
  depends_on = [time_sleep.wait_for_rbac_propagation]
}

output "key_vault_id" {
  value      = azurerm_key_vault.this.id
  depends_on = [time_sleep.wait_for_rbac_propagation]
}

output "key_vault_name" {
  value      = azurerm_key_vault.this.name
  depends_on = [time_sleep.wait_for_rbac_propagation]
}

output "key_vault_uri" {
  value      = azurerm_key_vault.this.vault_uri
  depends_on = [time_sleep.wait_for_rbac_propagation]
}
