# ADR-004: Geo-Redundant PostgreSQL Backup for Production

**Status:** Accepted  
**Date:** 2026-06-07  
**Deciders:** Platform Engineering  
**Tags:** reliability, Zero Trust, Azure PostgreSQL, FinOps, data protection

---

## Context

Azure Database for PostgreSQL Flexible Server provides two backup redundancy options:

- **Locally Redundant Backup (LRB):** Backups stored within a single Azure region. If the entire region becomes unavailable, backups are inaccessible until the region recovers.
- **Geo-Redundant Backup (GRB):** Backup data is replicated to a paired Azure region. If the primary region is unavailable, backups can be restored to the paired region.

The CNA platform stores engagement data — client network topology, findings, deliverables metadata — in PostgreSQL. This data is the core business artifact of the platform. A regional Azure outage that renders the database unrecoverable would result in permanent loss of completed engagement work.

Previously, `geo_redundant_backup_enabled = false` was hardcoded in the database module. This was appropriate for dev (cost savings, dev data is non-critical) but was incorrectly carrying over to production by default.

## Decision

Parameterize geo-redundant backup via a new `geo_redundant_backup_enabled` variable in `infra/terraform/providers/azure/database/variables.tf` (default `false`).

| Environment | `geo_redundant_backup_enabled` | `backup_retention_days` | SKU |
|---|---|---|---|
| Dev | `false` | 7 | `B_Standard_B1ms` |
| Prod | `true` | 30 | `GP_Standard_D2s_v3` |

Geo-redundant backup is enabled only for production. The 30-day retention window in prod aligns with common compliance requirements and provides a meaningful recovery timeline. Dev uses the minimum 7-day retention with local-only backup — adequate for development data and significantly cheaper.

**Note:** Geo-redundant backup requires a General Purpose or Memory Optimized SKU — it is not available on Burstable (`B_*`) SKUs. The prod database uses `GP_Standard_D2s_v3` (2 vCores, ~10 GB RAM), which satisfies this requirement.

## Consequences

**Positive:**
- Production engagement data can be restored in a paired region if the primary Azure region becomes unavailable — meets RPO/RTO objectives for a disaster recovery scenario
- 30-day retention provides recovery from scenarios discovered late (e.g., data corruption caused by a bug deployed weeks prior)
- The decision is captured in Terraform variables — toggling geo-redundancy is a `terraform apply` operation, not a manual portal change

**Negative / Risks:**
- Geo-redundant backup costs approximately 2x locally redundant backup. For the storage sizes used (64GB prod), this is a modest absolute cost but should be tracked in cost management dashboards.
- Geo-redundant backup is available in most Azure regions but not all. Verify availability in the target region before applying. If not available, the Terraform apply will fail.
- A regional restore creates a new server — connection strings, private DNS entries, and application configuration must be updated as part of the recovery runbook. This runbook does not yet exist and should be created as a follow-up.
- Geo-redundant backup does **not** provide real-time replication — it is a periodic backup, not a standby replica. For near-zero RTO, a read replica with failover promotion would be required (future consideration).

**Neutral:**
- Dev retains locally redundant backup. Dev engagement data is test/demo data without business value. Paying for geo-redundant backup in dev would provide no meaningful protection.
