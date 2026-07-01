# RBAC: managed identity needs Storage Blob Data Contributor to read/write engagements/ container.
resource "azurerm_role_assignment" "storage_blob_data_contributor" {
  for_each             = toset(var.storage_container_ids)
  scope                = each.value
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.managed_identity_principal_id
}

# NOTE: Key Vault Secrets Officer + Secrets User are already assigned in the
# identity module (on the managed identity itself). Do NOT add a Key Vault
# role assignment here — that would be a duplicate assignment on the same
# principal + scope, which Azure silently ignores but Terraform tracks as a
# separate resource, causing state drift.

# Sensitive platform secrets stored in Key Vault for the sync-env workflow to pull.
# These are the secrets that live ONLY in KV (not in security module):
#  - database-url            → full PostgreSQL connection string for Prisma
#  - nextauth-secret         → cryptographically random string for JWT signing
#  - entra-client-secret     → Entra ID OAuth2 client secret for NextAuth

resource "azurerm_key_vault_secret" "database_url" {
  name            = "cna-database-url"
  value           = var.database_url
  key_vault_id    = var.key_vault_id
  content_type    = "PostgreSQL connection string"
  expiration_date = var.secret_expiration_date

  lifecycle {
    # value: derived from module.database's connection string, which is stable
    # across applies unless the database module itself changes — ignoring it
    # avoids an unrelated apply (e.g. touching the database module) silently
    # rewriting this secret's value and expiration_date clock.
    # expiration_date: policy evaluates (expiry - version_created_date).
    # A metadata-only expiry update (no value change) fails policy because the
    # version's creation date is old. expiry is set correctly when value changes
    # (new KV version resets the creation date). Leave it alone between value changes.
    ignore_changes = [value, expiration_date]
  }
}

resource "azurerm_key_vault_secret" "nextauth_secret" {
  name            = "cna-nextauth-secret"
  value           = var.nextauth_secret
  key_vault_id    = var.key_vault_id
  content_type    = "Auth.js signing secret"
  expiration_date = var.secret_expiration_date

  lifecycle {
    # value: manually rotated in KV — don't overwrite with tfvar on every apply.
    # expiration_date: policy evaluates (expiry - original_created) not (expiry - now);
    # updating expiry on an existing version fails policy even with a short window.
    # Rotation resets the created date; expiry is managed at that point.
    ignore_changes = [value, expiration_date]
  }
}

resource "azurerm_key_vault_secret" "entra_client_secret" {
  name            = "cna-entra-client-secret"
  value           = var.entra_client_secret
  key_vault_id    = var.key_vault_id
  content_type    = "Entra ID OAuth client secret"
  expiration_date = var.secret_expiration_date

  lifecycle {
    ignore_changes = [value, expiration_date]
  }
}

resource "azurerm_key_vault_secret" "credential_encryption_key" {
  name            = "cna-credential-encryption-key"
  value           = var.credential_encryption_key
  key_vault_id    = var.key_vault_id
  content_type    = "AES-256 key for encrypting stored credentials"
  expiration_date = var.secret_expiration_date

  lifecycle {
    ignore_changes = [value, expiration_date]
  }
}

# Break-glass local admin: only created when the bootstrap script has
# generated and pushed the hash (var.local_admin_password != null). Existing
# environments that haven't bootstrapped this secret yet keep deploying
# unchanged — this resource simply doesn't exist for them.
resource "azurerm_key_vault_secret" "local_admin_password" {
  count           = var.local_admin_password != null ? 1 : 0
  name            = "cna-local-admin-password"
  value           = var.local_admin_password
  key_vault_id    = var.key_vault_id
  content_type    = "PBKDF2 hash of the break-glass local admin password"
  expiration_date = var.secret_expiration_date

  lifecycle {
    # value: rotated manually (delete the GitHub secret + re-run the
    # bootstrap script) — never overwritten by an unrelated apply.
    ignore_changes = [value, expiration_date]
  }
}
