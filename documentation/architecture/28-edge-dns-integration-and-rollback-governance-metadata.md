# 28 — Edge DNS Integration and Rollback Governance Metadata

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the governance-focused correction pass that strengthens Front Door custom-domain integration, TLS policy control, and rollback metadata selection rules.

---

## Objective

`28-edge-dns-integration-and-rollback-governance-metadata` adds Azure DNS zone integration inputs for Front Door custom domains, makes TLS policy settings explicit, and enriches release catalog metadata so rollback selection can require approved and healthy releases.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/security` | Adds Front Door custom-domain DNS zone integration and explicit TLS policy inputs |
| `.github/workflows/deploy-azure-runtime.yml` | Adds approval and health metadata to release catalog records and requires those markers during rollback resolution |

---

## Governance Impact

This pass improves governance by:
- enabling real DNS zone integration for Front Door custom domains
- making certificate policy inputs explicit instead of implicit defaults
- preventing rollback selection from choosing releases lacking approval and health metadata

---

## Remaining Gaps

Future work should still address:
- externalized health validation instead of workflow-assigned healthy status
- Key Vault-backed customer-managed certificate patterns for Front Door
- richer promotion and rollback policies tied to release validation evidence
