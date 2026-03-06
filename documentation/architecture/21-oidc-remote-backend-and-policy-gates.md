# 21 — OIDC, Remote Backend, and Policy Gates

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the next hardening pass for trusted Azure delivery and Terraform governance.

---

## Objective

`21-oidc-remote-backend-and-policy-gates` upgrades the deployment platform to use OpenID Connect authentication, explicit Azure remote backend configuration, and Terraform security gate enforcement.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `environments/azure/dev/providers.tf` | Enables AzureRM backend and provider OIDC support |
| `environments/azure/prod/providers.tf` | Enables AzureRM backend and provider OIDC support |
| `.github/workflows/deploy-azure-runtime.yml` | Uses Azure OIDC login, remote backend init inputs, scheduled drift detection, and tfsec policy gate |

---

## Required Repository Secrets

The workflow now expects:
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

---

## Required Repository Variables

The workflow now expects:
- `TFSTATE_RESOURCE_GROUP`
- `TFSTATE_STORAGE_ACCOUNT`
- `TFSTATE_CONTAINER`

---

## Governance Intent

This hardening pass removes static Azure credential dependence from the workflow design, introduces explicit remote backend wiring, and adds a Terraform security gate before plan/apply execution.
