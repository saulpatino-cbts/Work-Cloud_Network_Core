# 12 — Azure Storage Upload Integration

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first storage-backed publish integration for the hosted CNA Platform.

---

## Objective

`12-azure-storage-upload-integration` introduces engagement-scoped storage targeting so generated outputs can move from local staging toward Azure-backed delivery.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `apps/cna-api` | Publish response now includes target storage container and engagement blob prefix |
| `apps/cna-worker` | Worker computes engagement-scoped blob target paths for publish outputs |

---

## Integration Scope

This workstream adds:
- storage container awareness for published outputs
- engagement-scoped blob prefix convention
- first storage-targeting contract between application layer and Azure delivery surface

---

## Blob Path Convention

Published outputs should follow this pattern:

```text
engagements/{engagement_id}/{artifact_name}
```

This convention creates a clear per-engagement storage boundary for static-site artifacts and later downloadable deliverables.

---

## Next Steps

A later workstream should add:
- Azure Blob SDK upload implementation
- content-type aware uploads
- index and asset path conventions
- publish manifest generation
- storage-backed delivery metadata
