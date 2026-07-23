locals {
  # Mirrors Azure database's server_name/database_name derivation.
  instance_name = "${var.name_prefix}-pg"
  database_name = "cna"
}
