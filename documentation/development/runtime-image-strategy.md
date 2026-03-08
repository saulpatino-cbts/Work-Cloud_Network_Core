# Runtime Image Strategy

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first runtime image strategy for hosted CNA Platform services.

---

## Default Images

Terraform now supports explicit image inputs for:
- `cna-api`
- `cna-worker`

---

## Design Intent

The runtime image contract now belongs to Terraform inputs instead of being hardcoded to sample images.

This creates the path for CI/CD-driven image publication and environment-specific deployment promotion.
