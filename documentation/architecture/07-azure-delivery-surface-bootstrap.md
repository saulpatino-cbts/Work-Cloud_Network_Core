# 07 — Azure Delivery Surface Bootstrap

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first customer-facing delivery surface for the hosted CNA Platform on Azure.

---

## Objective

`07-azure-delivery-surface-bootstrap` formalizes how generated CNA artifacts are presented to customers through a static presentation layer.

---

## Delivered Module

| Module | Responsibility |
|---|---|
| `providers/azure/presentation` | Azure CDN-backed delivery surface for static CNA outputs |

---

## Delivery Model

The first Azure delivery surface uses:
- Blob static website hosting as the origin
- Azure CDN as the customer-facing endpoint

This model keeps delivery simple while still creating a clean separation between generated artifacts and the presentation endpoint.

---

## Artifact Publishing Path

```text
processing runtime
  -> generated deliverables
      -> static-site container / web endpoint
          -> Azure CDN endpoint
              -> customer-facing presentation URL
```

---

## Published Output Types

The delivery surface is intended to publish:
- static HTML summary views
- rendered diagrams
- downloadable documents
- report decks
- supporting visual artifacts

---

## Later Enhancements

A later workstream should add:
- custom domain support
- access control patterns for customer-specific delivery
- signed or time-bound artifact delivery where needed
- automated publish workflows from CNA worker outputs
