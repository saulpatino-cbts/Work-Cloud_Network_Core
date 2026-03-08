locals {
  key_vault_name        = substr(replace(lower("kv-${var.name_prefix}-platform"), "_", "-"), 0, 24)
  managed_identity_name = "id-${var.name_prefix}-platform"
}
