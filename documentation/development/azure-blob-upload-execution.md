# Azure Blob Upload Execution

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first executable upload contract for Azure-backed publishing.

---

## Upload Controls

Environment variables:
- `CNA_STORAGE_STATIC_CONTAINER`
- `CNA_BLOB_UPLOAD_ENABLED`
- `CNA_BLOB_UPLOAD_MODE`

---

## Execution Shape

The worker upload flow now returns a structured result with:
- execution mode
- target container
- target blob path
- local source path

---

## Design Intent

This keeps the upload workflow explicit and testable before the Azure Blob SDK is added.
