# 24 — Cleanup and Correction Toward a Coherent Azure Reference Architecture

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document captures the cleanup-and-correction pass that normalizes earlier hardening work into a more coherent Azure delivery architecture.

---

## Objective

`24-cleanup-and-correction-toward-a-coherent-azure-reference-architecture` connects API origin routing to Front Door, enables internal-only runtime ingress by environment configuration, persists release catalog records in-repo, and adds automatic rollback target discovery from the environment release catalog.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/security` | Connects Front Door origin/routing to the API runtime endpoint and exposes Front Door endpoint output |
| `environments/azure/dev` | Enables internal-only Container Apps deployment mode and passes API FQDN to security edge resources |
| `environments/azure/prod` | Enables internal-only Container Apps deployment mode and passes API FQDN to security edge resources |
| `.github/workflows/deploy-azure-runtime.yml` | Persists release catalog entries in-repo and resolves rollback targets automatically from latest environment catalog state |

---

## Design Corrections

This pass corrects several earlier issues by:
- wiring Front Door to an actual API origin host
- making runtime ingress intent explicit in environment configuration
- converting release cataloging from transient artifact-only behavior into repo-tracked state
- reducing manual rollback target selection through environment catalog lookup

---

## Remaining Gaps

Future work should still address:
- full VNet and subnet integration for Container Apps environments
- private endpoints for storage, Key Vault, and AI dependencies
- custom domain and certificate binding for Front Door
- stronger rollback selection logic beyond latest successful record
