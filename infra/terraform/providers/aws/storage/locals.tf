locals {
  # Mirrors Azure storage's blob_containers list exactly -- same four logical
  # buckets, S3-equivalent naming once the bucket-per-purpose vs prefix-per-purpose
  # decision is made.
  buckets = [
    "raw-artifacts",
    "normalized-artifacts",
    "deliverables",
    "static-site",
  ]
}
