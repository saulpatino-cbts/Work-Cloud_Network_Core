# 19 — Terraform Plan, Approval, and State Hardening

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first deployment safety hardening for Azure runtime promotion.

---

## Objective

`19-terraform-plan-approval-and-state-hardening` upgrades the deployment workflow to introduce plan/apply separation, approval support, and an initial remote state key strategy.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Adds Terraform plan, artifact handoff, and gated apply behavior |

---

## Safety Model

The workflow now introduces:
- Terraform formatting validation
- Terraform configuration validation
- Terraform plan generation before apply
- artifact handoff between plan and apply stages
- production approval gate through GitHub environment protection

For production, the workflow targets the `prod-approval` environment for apply-stage approval.

---

## State Strategy

The workflow now initializes Terraform with an environment-scoped backend key:
- `dev.terraform.tfstate`
- `prod.terraform.tfstate`

This is the first state isolation convention for hosted environment promotion.

---

## Required Secrets and Configuration

The workflow expects:
- `AZURE_CREDENTIALS`

Repository environments should include:
- `dev`
- `prod`
- `prod-approval`

---

## Next Steps

A later workstream should add:
- explicit remote backend storage configuration
- drift detection workflow
- rollback workflow support
- signed deployment provenance
- release-to-deploy traceability
