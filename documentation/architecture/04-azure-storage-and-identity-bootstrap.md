# 04 — Azure Storage and Identity Bootstrap

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first implemented Azure workload modules for the CNA Platform.

---

## Objective

`04-azure-storage-and-identity-bootstrap` adds the first reusable provider-specific Terraform modules for Azure.

These modules establish:
- artifact storage
- static website endpoint foundation
- managed identity
- Key Vault foundation

---

## Delivered Modules

| Module | Responsibility |
|---|---|
| `providers/azure/storage` | Storage account and assessment artifact containers |
| `providers/azure/identity` | User-assigned managed identity and Key Vault |

---

## Why These First

Storage and identity are the most foundational hosted platform capabilities.

Compute, ingress, AI, and presentation workloads all depend on them either directly or indirectly.

---

## Storage Containers

The Azure storage module provisions these blob containers:
- `raw-artifacts`
- `normalized-artifacts`
- `deliverables`
- `static-site`

---

## Identity Foundation

The Azure identity module provisions:
- user-assigned managed identity
- Key Vault

These resources form the base for secure service-to-service access in later workstreams.
