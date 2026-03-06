# 26 — Private Endpoints and Private DNS Wiring

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the dependency-side private connectivity pass for the hosted CNA Platform.

---

## Objective

`26-private-endpoints-and-private-dns-wiring` adds private DNS zones, virtual network links, and private endpoints for storage, Key Vault, and Azure OpenAI connectivity patterns.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/security` | Adds private DNS zones, VNet links, and private endpoints for dependency connectivity |
| `environments/azure/dev` | Passes VNet, private endpoint subnet, and storage identifiers into security module |
| `environments/azure/prod` | Passes VNet, private endpoint subnet, and storage identifiers into security module |

---

## Architecture Impact

This pass adds:
- private DNS zone foundations for blob, Key Vault, and OpenAI
- VNet links for dependency name resolution
- private endpoint resources for storage blob and Key Vault
- OpenAI private connectivity scaffolding through dedicated private endpoint pattern

---

## Remaining Gaps

Future work should still address:
- aligning private endpoint resources to the actual AI module resource IDs instead of temporary scaffolding
- custom domain and certificate binding for Front Door
- refined rollback selection intelligence
