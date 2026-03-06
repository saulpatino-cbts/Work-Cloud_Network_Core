# 10 — Application Skeleton

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first hosted application skeleton for the CNA Platform.

---

## Objective

`10-application-skeleton` introduces the first runnable application-layer structure for the hosted CNA Platform.

This workstream provides minimal application scaffolding so the infrastructure no longer depends only on placeholder concepts.

---

## Delivered Components

| Component | Responsibility |
|---|---|
| `apps/cna-api` | Intake API and health endpoint skeleton |
| `apps/cna-worker` | Worker bootstrap entry point for async processing |

---

## API Skeleton

The first API skeleton includes:
- `/health` endpoint
- `/intake` endpoint
- request model for engagement intake metadata

This is intentionally minimal and is a platform bootstrap, not a final application design.

---

## Worker Skeleton

The first worker skeleton includes:
- Python entry point
- working directory bootstrap
- placeholder runtime startup behavior

This creates the minimum structure needed to evolve into normalization, analysis, diagram, and reporting jobs.

---

## Next Application Steps

A later workstream should add:
- artifact upload handling
- queue-driven job dispatch
- storage integration
- Key Vault secret retrieval
- Azure OpenAI integration
- publish flow into the delivery surface
