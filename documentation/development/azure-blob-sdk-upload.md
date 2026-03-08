# Azure Blob SDK Upload

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first SDK-backed Azure Blob upload behavior in the hosted CNA Platform.

---

## Upload Method

The worker now uses:
- `DefaultAzureCredential`
- `BlobServiceClient`
- `ContentSettings`

This is the first real cloud-backed publish path in the platform.

---

## Execution Rules

- If upload is disabled, the worker returns a skipped result.
- If the storage account name is missing, the worker returns an error result.
- If upload is enabled and configuration is present, the worker uploads the file to Azure Blob Storage.
