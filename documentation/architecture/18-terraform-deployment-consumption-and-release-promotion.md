# 18 — Terraform Deployment Consumption and Release Promotion

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first deployment workflow that consumes published runtime images and applies them to Azure environments.

---

## Objective

`18-terraform-deployment-consumption-and-release-promotion` introduces a deployment workflow so environment-specific Azure runtime deployments can consume published image references.

---

## Delivered Workflow

| Workflow | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Apply Azure environment Terraform using selected runtime image references |

---

## Release Promotion Model

The first release promotion model is manual and workflow-driven.

The deploy workflow accepts:
- target environment (`dev` or `prod`)
- API image reference
- worker image reference

This establishes the first controlled promotion path between published images and runtime environments.

---

## Required Secret

The workflow expects:
- `AZURE_CREDENTIALS`

---

## Next Steps

A later workstream should add:
- automatic promotion rules
- Terraform plan and approval stages
- environment-specific state backends
- release provenance tracking
- rollback workflow support
