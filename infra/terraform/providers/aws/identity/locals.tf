locals {
  # Mirrors Azure identity's key_vault_name/managed_identity_name derivation.
  secret_prefix = var.name_prefix
  role_name     = "${var.name_prefix}-role"
}
