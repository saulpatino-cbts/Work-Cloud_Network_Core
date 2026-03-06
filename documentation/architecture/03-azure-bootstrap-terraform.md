# 03 — Azure Bootstrap Terraform

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first runnable Terraform slice for the CNA Platform on Azure.

---

## Objective

`03-azure-bootstrap-terraform` creates the first deployable Azure-hosted CNA Platform baseline.

This bootstrap targets the minimum hosted platform slice needed to accept uploads, process workloads, integrate AI, and present generated outputs.

---

## First Azure Slice

The first Terraform implementation targets these workloads:

1. ingress
2. storage
3. compute
4. ai
5. presentation
6. identity
7. observability

---

## Azure Service Selection

| Workload | Azure Service |
|---|---|
| Ingress | Azure Container Apps ingress |
| Storage | Azure Storage Account with Blob containers |
| Compute | Azure Container Apps |
| AI | Azure OpenAI |
| Presentation | Azure Static Web Apps or Blob static website |
| Identity | Managed Identity + Key Vault |
| Observability | Log Analytics + Application Insights |

---

## Bootstrap Design Principles

- Managed services first
- Container-first runtime
- Minimal networking complexity for first slice
- Native identity before secrets
- Artifact storage separated by lifecycle
- Static delivery surface generated from platform outputs

---

## Planned Terraform Deliverables

- Azure provider bootstrap
- Resource group and naming locals
- Storage account and blob containers
- Container Apps environment
- Container app for CNA API / ingress
- Container app for CNA worker runtime
- Azure OpenAI account wiring inputs
- Key Vault and managed identity wiring
- Log Analytics workspace and monitoring hooks
- Static website or Static Web App skeleton
