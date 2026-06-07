# ADR-002: Environment-Differentiated Storage Replication and Blob Lifecycle Tiering

**Status:** Accepted  
**Date:** 2026-06-07  
**Deciders:** Platform Engineering  
**Tags:** FinOps, storage, Azure Storage, reliability

---

## Context

The CNA platform uses a single Azure Storage Account per environment to store raw network assessment artifacts (`raw-artifacts/` container) and processed client deliverables (`deliverables/` container). Two concerns drove this decision:

**1. Replication type was hardcoded to LRS in all environments.** Locally Redundant Storage (LRS) stores three copies within a single datacenter. This is cost-optimal for dev, but for production it creates a single-datacenter failure risk — if the datacenter goes offline, the storage account is unavailable. Zone-Redundant Storage (ZRS) distributes copies across three availability zones in the same region, providing resilience against datacenter-level failures at a modest cost premium (~25% over LRS).

**2. No lifecycle management policy existed.** Raw assessment artifacts can be large (network topology dumps, packet captures, scan results). Without a tiering policy, all blobs remain in the Hot tier indefinitely, incurring Hot-tier storage and retrieval costs even for data that is rarely accessed after initial processing. Deliverables (PDFs, reports) have longer value lifespans but are also eventually superseded.

## Decision

### Replication

- **Dev:** `account_replication_type = "LRS"` — lowest cost, single-datacenter redundancy is acceptable for non-critical data
- **Prod:** `account_replication_type = "ZRS"` — zone-redundant, protects against single-AZ failure

The replication type is controlled via a new `replication_type` variable in `infra/terraform/providers/azure/storage/variables.tf` (default `"LRS"`).

### Lifecycle Tiering

A `azurerm_storage_management_policy` resource is added to the storage module with two rules:

| Prefix | Action | Trigger |
|---|---|---|
| `raw-artifacts/` | Move to Cool tier | After 30 days since last modification |
| `raw-artifacts/` | Delete | After 365 days since last modification |
| `deliverables/` | Move to Cool tier | After 90 days since last modification |

The retention thresholds are parameterized (`raw_artifact_retention_days`, `deliverable_retention_days`) and can be tuned per environment. Setting a value to `0` disables the rule for that prefix.

Cool tier pricing is approximately 50% of Hot tier for storage costs, with slightly higher retrieval costs — appropriate for data that is accessed infrequently after initial ingestion.

## Consequences

**Positive:**
- Production storage is zone-resilient without cross-region replication cost (GRS would be 2–4x more expensive)
- Raw artifacts automatically reduce cost as they age — a large assessment run's data drops to Cool tier after a month
- Deliverables that are superseded by newer versions are eventually cleaned up automatically
- All thresholds are Terraform variables — adjustable without module changes

**Negative / Risks:**
- Cool tier has higher per-operation retrieval costs. If a report rendering pipeline re-reads raw artifacts frequently after 30 days, retrieval costs could offset the storage savings. This should be monitored via Azure Cost Management.
- The 365-day delete threshold for raw artifacts is permanent. Before this policy was applied, artifacts were retained indefinitely. Any compliance requirement for longer retention must be handled by exporting to an Archive tier or a separate long-term storage account before deletion occurs.
- ZRS is not available in all Azure regions. If the deployment region is changed to one that doesn't support ZRS, the `replication_type = "ZRS"` setting will cause a Terraform error. Validate region support before deploying prod to a new region.

**Neutral:**
- `versioning_enabled = false` is explicitly set. Enabling versioning would prevent the lifecycle policy from deleting blobs with retained versions. This is intentional — version history is not needed for this workload.
