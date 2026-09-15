resource "azurerm_storage_account" "this" {
  #checkov:skip=CKV2_AZURE_1:Customer-managed key support is deferred until Key Vault key lifecycle and application access are validated.
  #checkov:skip=CKV2_AZURE_33:Private endpoint is created in the security module and wired to this account through its resource ID.
  #checkov:skip=CKV_AZURE_33:Queue service logging is not applicable; the platform does not use Azure Queue Storage.
  #checkov:skip=CKV_AZURE_59:Terraform apply needs temporary public data-plane access for storage account bootstrap and static website resources.
  #checkov:skip=CKV2_AZURE_40:Terraform apply requires Shared Key authorization during bootstrap because the provider uses data-plane operations before private endpoint approvals.
  name                            = local.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = var.replication_type
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = true
  shared_access_key_enabled       = true
  tags                            = var.tags

  sas_policy {
    expiration_period = "1.00:00:00"
    expiration_action = "Log"
  }

  blob_properties {
    # Zero Trust: prevent accidental public exposure
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  # Deny-by-default data-plane firewall. Application traffic reaches this account
  # over the private endpoint created in the security module; the AzureServices
  # bypass keeps Azure platform access (diagnostics, static-website provisioning)
  # working. public_network_access_enabled stays true because Terraform apply and
  # the static-website bootstrap need a data-plane window, but leaving
  # default_action at its implicit "Allow" exposed the account to every source IP
  # on the internet. The deploy/drift workflows add and remove the transient
  # runner IP the same way they do for the Key Vault (identity module), so that
  # ephemeral ip_rules entry must not fight Terraform.
  network_rules {
    bypass         = ["AzureServices"]
    default_action = "Deny"
  }

  lifecycle {
    ignore_changes = [network_rules[0].ip_rules]
  }

}

resource "azurerm_storage_account_static_website" "this" {
  storage_account_id = azurerm_storage_account.this.id
  index_document     = "index.html"
  error_404_document = "404.html"
}

resource "azurerm_storage_container" "containers" {
  #checkov:skip=CKV2_AZURE_21:Blob diagnostic logging will be enforced through Azure Monitor once the shared observability workspace is exposed to this module.
  for_each              = toset(local.blob_containers)
  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
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
