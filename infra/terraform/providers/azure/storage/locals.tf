locals {
  storage_account_name = substr(replace(lower("st${var.name_prefix}platform"), "-", ""), 0, 24)
  blob_containers = [
    "raw-artifacts",
    "normalized-artifacts",
    "deliverables",
    "static-site"
  ]
}
