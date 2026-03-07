# RBAC: managed identity needs Storage Blob Data Contributor to read/write engagements/ container.
resource "azurerm_role_assignment" "storage_blob_data_contributor" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.managed_identity_principal_id
}

# NOTE: Key Vault Secrets Officer is already assigned in the security module.
# Do NOT add Key Vault Secrets User here — that would be a duplicate assignment
# on the same principal + scope, which Azure silently ignores but Terraform tracks
# as a separate resource, causing state drift.

# Sensitive platform secrets stored in Key Vault for the sync-env workflow to pull.
# These are the secrets that live ONLY in KV (not in security module):
#  - database-url            → full PostgreSQL connection string for Prisma
#  - nextauth-secret         → cryptographically random string for JWT signing
#  - entra-client-secret     → Entra ID OAuth2 client secret for NextAuth

resource "azurerm_key_vault_secret" "database_url" {
  name         = "cna-database-url"
  value        = var.database_url
  key_vault_id = var.key_vault_id

  lifecycle {
    # Password rotation is handled outside Terraform via Key Vault rotation policy.
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "nextauth_secret" {
  name         = "cna-nextauth-secret"
  value        = var.nextauth_secret
  key_vault_id = var.key_vault_id

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "entra_client_secret" {
  name         = "cna-entra-client-secret"
  value        = var.entra_client_secret
  key_vault_id = var.key_vault_id

  lifecycle {
    ignore_changes = [value]
  }
}
