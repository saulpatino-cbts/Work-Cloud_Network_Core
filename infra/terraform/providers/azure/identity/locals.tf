locals {
  key_vault_name        = substr(lower("${var.name_prefix}-kv"), 0, 24)
  managed_identity_name = "${var.name_prefix}-id"
}
