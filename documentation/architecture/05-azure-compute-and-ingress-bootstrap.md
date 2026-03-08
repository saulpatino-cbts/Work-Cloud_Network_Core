# 05 — Azure Compute and Ingress Bootstrap

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the next Azure bootstrap slice for hosted CNA runtime workloads.

---

## Objective

`05-azure-compute-and-ingress-bootstrap` adds the first hosted application runtime for the CNA Platform on Azure.

This slice establishes:
- managed container runtime
- API ingress surface
- worker execution surface
- log workspace foundation for runtime telemetry

---

## Delivered Module

| Module | Responsibility |
|---|---|
| `providers/azure/compute` | Container Apps environment, API app, worker app, runtime logging foundation |

---

## Runtime Model

The first Azure runtime uses Azure Container Apps.

Two initial applications are deployed:
- `cna-api` for uploads, intake, API workflows, and platform ingress
- `cna-worker` for asynchronous processing, normalization, analysis, diagrams, and report generation

---

## Ingress Position

The API app exposes external ingress.

The worker app does not expose external ingress in this first bootstrap slice.

---

## Placeholder Runtime Images

The first module uses placeholder container images so the platform runtime can be provisioned before final CNA application images are published.

These images must be replaced with CNA platform images in a later workstream.
