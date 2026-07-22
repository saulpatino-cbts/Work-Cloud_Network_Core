# =============================================================================
# RDS PostgreSQL (equivalent to Azure PostgreSQL Flexible Server)
# =============================================================================

resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-psql"

  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  multi_az               = var.db_multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = var.db_backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"

  skip_final_snapshot       = var.environment == "dev"
  final_snapshot_identifier = var.environment == "dev" ? null : "${local.name_prefix}-psql-final"
  deletion_protection       = var.environment != "dev"

  publicly_accessible = false

  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = { Name = "${local.name_prefix}-psql" }

  lifecycle {
    ignore_changes = [password]
  }
}
