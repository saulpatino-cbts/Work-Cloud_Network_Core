# 11 — Publish Flow and Runtime Integration

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first integration path between the hosted CNA application layer and the Azure delivery surface.

---

## Objective

`11-publish-flow-and-runtime-integration` connects the application skeleton to the artifact lifecycle and static delivery model.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `apps/cna-api` | Publish endpoint scaffold for delivery workflow initiation |
| `apps/cna-worker` | Local artifact workspace bootstrap and placeholder publish behavior |

---

## Publish Flow

The first publish flow is intentionally minimal and establishes the control path only.

```text
intake / processing
  -> deliverable artifact creation
      -> static-site staging path
          -> delivery surface publication
```

---

## API Role

The API layer now includes a publish endpoint scaffold.

This provides the first control-plane entry point for future artifact promotion workflows.

---

## Worker Role

The worker layer now creates a local artifact directory structure and publishes a placeholder HTML summary into the static-site path.

This demonstrates the shape of the artifact lifecycle before cloud storage upload behavior is added.

---

## Next Integration Steps

A later workstream should add:
- Azure Blob Storage upload implementation
- engagement-scoped output structures
- CDN publication invalidation strategy
- queue-driven publish jobs
- storage-backed artifact metadata tracking
