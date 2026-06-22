output "server_id" {
  description = "PostgreSQL Flexible Server resource ID"
  value       = azurerm_postgresql_flexible_server.this.id
}

output "server_name" {
  description = "PostgreSQL Flexible Server name"
  value       = azurerm_postgresql_flexible_server.this.name
}

output "server_fqdn" {
  description = "PostgreSQL Flexible Server FQDN (private DNS name)"
  value       = azurerm_postgresql_flexible_server.this.fqdn
}

output "database_name" {
  description = "Application database name"
  value       = azurerm_postgresql_flexible_server_database.app.name
}

output "connection_string" {
  description = "DATABASE_URL for Prisma / SQLAlchemy. Contains admin password — treat as sensitive."
  value       = "postgresql://${var.admin_username}:${urlencode(var.admin_password)}@${azurerm_postgresql_flexible_server.this.fqdn}:5432/${local.database_name}?sslmode=require"
  sensitive   = true
}
