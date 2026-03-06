# Publish Flow

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the initial publish lifecycle for hosted CNA artifacts.

---

## Lifecycle Stages

1. Artifact intake
2. Processing and generation
3. Deliverable staging
4. Static-site publication
5. Customer delivery via presentation endpoint

---

## Initial File Model

The first local workspace model uses these directories:
- `raw-artifacts`
- `normalized-artifacts`
- `deliverables`
- `static-site`

---

## Design Intent

The publish flow is split into two concerns:
- application-side generation and staging
- platform-side presentation and delivery

This keeps artifact creation separate from customer-facing publication.
