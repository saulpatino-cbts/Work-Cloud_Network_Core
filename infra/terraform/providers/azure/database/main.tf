# PostgreSQL Flexible Server — private, VNet-integrated, no public access.
# Uses a dedicated delegated subnet (NOT a private endpoint).
# The private DNS zone must exist before this resource — it is created in
# the security module and its ID passed in via var.postgres_private_dns_zone_id.

resource "azurerm_postgresql_flexible_server" "this" {
  #checkov:skip=CKV2_AZURE_57:Flexible Server is private through delegated subnet plus private DNS; this is the intended Azure private access model.
  name                          = local.server_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = var.postgres_version
  delegated_subnet_id           = var.db_subnet_id
  private_dns_zone_id           = var.postgres_private_dns_zone_id
  administrator_login           = var.admin_username
  administrator_password        = var.admin_password
  public_network_access_enabled = false

  storage_mb = var.storage_mb
  sku_name   = var.sku_name

  backup_retention_days        = var.backup_retention_days
  geo_redundant_backup_enabled = var.geo_redundant_backup_enabled

  dynamic "high_availability" {
    for_each = var.high_availability_enabled ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      # Password rotation is handled outside Terraform via Key Vault.
      administrator_password,
      # Zone is auto-assigned by Azure on create.
      zone,
      # high_availability.mode is set once at create time via var.high_availability_enabled
      # above; Azure may reassign the standby zone independently afterward, so drift on
      # the block itself is ignored post-creation rather than fought on every apply.
      high_availability
    ]
  }
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = local.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "utf8"
  collation = "en_US.utf8"
}

# Allow extensions needed by Prisma / CNA schema.
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "uuid-ossp,pgcrypto"
}
