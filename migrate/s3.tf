# =============================================================================
# S3 Buckets (equivalent to Azure Storage Account)
# =============================================================================

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name_prefix}-artifacts-${random_id.bucket_suffix.hex}"
  tags   = { Name = "${local.name_prefix}-artifacts" }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "raw-artifacts-tiering"
    status = "Enabled"
    filter { prefix = "raw-artifacts/" }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    expiration { days = 365 }
  }

  rule {
    id     = "deliverables-tiering"
    status = "Enabled"
    filter { prefix = "deliverables/" }
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}

# Static website hosting bucket (equivalent to Azure Static Website)
resource "aws_s3_bucket" "static_site" {
  bucket = "${local.name_prefix}-static-${random_id.bucket_suffix.hex}"
  tags   = { Name = "${local.name_prefix}-static" }
}

resource "aws_s3_bucket_public_access_block" "static_site" {
  bucket                  = aws_s3_bucket.static_site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
