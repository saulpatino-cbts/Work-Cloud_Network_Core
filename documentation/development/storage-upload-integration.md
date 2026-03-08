# Storage Upload Integration

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first application-layer contract for Azure storage-backed publishing.

---

## Container Contract

The initial publish flow uses the `static-site` container as the target delivery container.

Environment variable:
- `CNA_STORAGE_STATIC_CONTAINER`

---

## Path Contract

Published artifacts use engagement-scoped blob paths:

```text
engagements/{engagement_id}/{artifact_name}
```

---

## Design Intent

This contract allows the worker and API layers to agree on delivery target shape before Azure Blob SDK upload code is implemented.
