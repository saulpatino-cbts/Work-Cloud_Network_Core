# 08 — Runtime Wiring and Secrets

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first secure runtime integration slice for the hosted CNA Platform on Azure.

---

## Objective

`08-runtime-wiring-and-secrets` connects the hosted CNA runtime to the platform resources it depends on.

This workstream moves the platform from adjacent resources to an integrated hosted runtime.

---

## Delivered Module

| Module | Responsibility |
|---|---|
| `providers/azure/runtime` | Managed identity role assignments and runtime app settings wiring |

---

## Runtime Wiring Scope

This workstream establishes:
- managed identity authorization to storage
- managed identity authorization to Key Vault
- application settings for storage account access
- application settings for Azure OpenAI endpoint usage
- application settings for Application Insights telemetry

---

## Platform Effect

After this workstream, the hosted CNA runtime has the first formal path to:
- reach assessment artifact storage
- retrieve secrets from Key Vault
- call Azure OpenAI using configured runtime settings
- emit telemetry through Application Insights

---

## Next Hardening Items

A later workstream should add:
- Key Vault secret references instead of raw runtime values where applicable
- user-assigned identity binding directly to runtime apps
- deeper least-privilege role scoping
- secret inventory and rotation references
- alerting and dashboard definitions
