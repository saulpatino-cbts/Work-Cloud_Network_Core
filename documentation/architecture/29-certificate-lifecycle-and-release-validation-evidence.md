# 29 — Certificate Lifecycle and Release Validation Evidence

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the final governance-focused pass that strengthens certificate lifecycle controls and release evidence requirements.

---

## Objective

`29-certificate-lifecycle-and-release-validation-evidence` adds customer-managed Front Door certificate support through Key Vault secret IDs and enriches release catalog metadata with validation checks so rollback decisions can require stronger evidence than simple status fields.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/security` | Adds customer-managed Front Door secret support for Key Vault-backed certificates |
| `.github/workflows/deploy-azure-runtime.yml` | Adds validation check metadata and requires successful validation evidence during rollback selection |

---

## Governance Impact

This pass improves governance by:
- supporting customer-managed certificate patterns for Front Door via Key Vault-backed secrets
- recording deployment validation evidence in release catalog entries
- requiring validation evidence in addition to approval and health metadata for rollback eligibility

---

## Remaining Gaps

Future work should still address:
- independent external health probes instead of workflow-internal evidence assignment
- richer promotion policy tied to staged verification signals
- automated certificate rotation lifecycle governance
