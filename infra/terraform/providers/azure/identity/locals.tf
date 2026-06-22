locals {
  key_vault_name        = substr(lower("${var.name_prefix}-kv${var.key_vault_name_suffix}"), 0, 24)
  managed_identity_name = "${var.name_prefix}-id"
}
