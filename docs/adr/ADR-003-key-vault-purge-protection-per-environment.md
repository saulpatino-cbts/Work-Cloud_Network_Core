# ADR-003: Environment-Differentiated Key Vault Soft Delete and Purge Protection

**Status:** Accepted  
**Date:** 2026-06-07  
**Deciders:** Platform Engineering, Security  
**Tags:** Zero Trust, secrets management, Azure Key Vault, compliance

---

## Context

Azure Key Vault supports two layered deletion protections:

- **Soft delete:** When enabled, deleted secrets/keys/certificates enter a "deleted" state for a configurable retention period (7–90 days) before being permanently removed. They can be recovered during this window.
- **Purge protection:** When enabled, secrets cannot be permanently deleted (purged) even by administrators during the soft-delete retention window. Only the automatic expiry of the retention period triggers permanent deletion.

Previously, the CNA platform's Key Vault was provisioned with hardcoded values: `soft_delete_retention_days = 7` and `purge_protection_enabled = false`. This is appropriate for dev (short retention, no protection overhead), but insufficient for production where:

1. A production secret being accidentally deleted and permanently purged before recovery could cause a platform outage
2. Compliance frameworks (SOC 2, ISO 27001, NIST 800-53 SC-12) require demonstrable controls around cryptographic key and secret lifecycle management
3. An attacker who gains temporary Key Vault Secrets Officer access should not be able to irreversibly destroy secrets — purge protection limits the blast radius of a compromised identity

## Decision

Parameterize Key Vault soft-delete retention and purge protection via new variables in `infra/terraform/providers/azure/identity/variables.tf`:

| Variable | Dev | Prod |
|---|---|---|
| `key_vault_soft_delete_retention_days` | 7 | 90 |
| `key_vault_purge_protection_enabled` | `false` | `true` |

**Dev:** 7-day retention and no purge protection — allows rapid teardown/recreate cycles during development. A dev Key Vault with purge protection enabled cannot be purged for 7 days after deletion, which blocks `terraform destroy` and re-creates.

**Prod:** 90-day retention (maximum) with purge protection enabled. This means:
- Any deleted secret is recoverable for up to 90 days
- No identity — including subscription Owners — can permanently destroy a secret within that window
- After 90 days, soft-deleted secrets are automatically purged

## Consequences

**Positive:**
- Accidental secret deletion in production is recoverable for 90 days
- Purge protection prevents a compromised admin credential from being used to irreversibly destroy secrets (Zero Trust: assume breach)
- 90-day retention aligns with common compliance audit cycle lengths — evidence of secret existence is preserved through audit periods
- The `terraform destroy` workflow for prod is not blocked — purge protection only prevents *purge* of deleted vaults/secrets, not normal Terraform operations on live resources

**Negative / Risks:**
- Once `purge_protection_enabled = true` is applied to a Key Vault, it **cannot be disabled**. This is enforced by Azure. If the vault needs to be destroyed and recreated quickly (e.g., region migration), the old vault will block reuse of the same name for 90 days. Name it with a unique suffix or use `terraform import` to adopt the existing vault.
- If a prod deployment is torn down with `terraform destroy` and the Key Vault enters soft-delete, Terraform cannot recreate it at the same name for 90 days. The workaround is to explicitly purge after the retention period, or provision with a new name.
- Dev deployments retain 7-day soft delete (Azure minimum). This means deleting and recreating dev infrastructure within 7 days of teardown requires either recovering or purging the old vault first.

**Neutral:**
- Azure Key Vault soft delete has been mandatory since February 2025 and cannot be disabled. This ADR governs the retention duration and purge protection flag, not whether soft delete is used.
