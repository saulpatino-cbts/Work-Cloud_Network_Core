locals {
  storage_account_name = substr(replace(lower("${var.name_prefix}st"), "-", ""), 0, 24)
  blob_containers = [
    "raw-artifacts",
    "normalized-artifacts",
    "deliverables",
    "static-site"
  ]
}
