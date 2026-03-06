# 14 — Azure Blob SDK Integration

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first real Azure Blob SDK integration for the hosted CNA Platform publish flow.

---

## Objective

`14-azure-blob-sdk-integration` replaces placeholder upload execution with Azure Blob Storage SDK-backed publishing behavior.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `apps/cna-api` | Publish response now surfaces upload mode alongside upload enablement |
| `apps/cna-worker` | Worker performs Azure Blob SDK upload using DefaultAzureCredential when enabled |

---

## Runtime Behavior

When blob upload is enabled:
- the worker resolves the storage account name from runtime configuration
- authenticates using `DefaultAzureCredential`
- uploads the generated file into Azure Blob Storage
- sets a basic content type for HTML artifacts

When blob upload is disabled, the worker returns a structured skipped result.

---

## Required Runtime Settings

- `CNA_STORAGE_ACCOUNT_NAME`
- `CNA_STORAGE_STATIC_CONTAINER`
- `CNA_BLOB_UPLOAD_ENABLED`
- `CNA_BLOB_UPLOAD_MODE`

---

## Next Steps

A later workstream should add:
- managed identity verification in Container Apps
- richer content-type handling for images, decks, and documents
- retry and error-handling strategy
- publish manifest generation
- CDN invalidation and presentation refresh behavior
