resource "azurerm_storage_account" "this" {
  name                     = local.storage_account_name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.replication_type
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"
  tags                     = var.tags

  blob_properties {
    # Zero Trust: prevent accidental public exposure
    versioning_enabled = false
  }

}

resource "azurerm_storage_account_static_website" "this" {
  storage_account_id = azurerm_storage_account.this.id
  index_document     = "index.html"
  error_404_document = "404.html"
}

resource "azurerm_storage_container" "containers" {
  for_each              = toset(local.blob_containers)
  name                  = each.value
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}

# FinOps: lifecycle policy — move old raw artifacts to Cool tier, delete very old ones
resource "azurerm_storage_management_policy" "lifecycle" {
  storage_account_id = azurerm_storage_account.this.id

  rule {
    name    = "raw-artifacts-tiering"
    enabled = var.raw_artifact_retention_days > 0

    filters {
      prefix_match = ["raw-artifacts/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        # Move to Cool tier after retention_days — ~50% cost reduction
        tier_to_cool_after_days_since_modification_greater_than = var.raw_artifact_retention_days
        # Delete after 365 days to prevent unbounded storage growth
        delete_after_days_since_modification_greater_than = 365
      }
    }
  }

  rule {
    name    = "deliverables-tiering"
    enabled = var.deliverable_retention_days > 0

    filters {
      prefix_match = ["deliverables/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        # Deliverables are accessed less frequently — move to Cool after retention period
        tier_to_cool_after_days_since_modification_greater_than = var.deliverable_retention_days
      }
    }
  }
}
