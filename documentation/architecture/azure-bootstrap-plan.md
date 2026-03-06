# Azure Bootstrap Plan

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first Azure deployment plan for the hosted CNA Platform.

---

## Resource Groups

Recommended initial resource grouping:

- `rg-cna-platform-dev`
- `rg-cna-platform-prod`

Optional later split:
- `rg-cna-network-*`
- `rg-cna-data-*`
- `rg-cna-ai-*`

For the first bootstrap, use a single resource group per environment for simplicity.

---

## Storage Layout

Blob containers should be separated by responsibility:

- `raw-artifacts`
- `normalized-artifacts`
- `deliverables`
- `static-site`

---

## Container Workloads

Initial containerized workloads:

- `cna-api` — ingress and assessment intake
- `cna-worker` — processing, analysis, diagram generation, and report generation

These should share a managed environment but remain separate applications.

---

## Identity Model

Use system-assigned or user-assigned managed identity for runtime access.

Managed identity should be granted:
- Key Vault Secrets User
- Storage Blob Data Contributor
- Azure OpenAI access as required by chosen service pattern

---

## Monitoring Model

The first slice should send runtime logs and app telemetry to:
- Log Analytics workspace
- Application Insights

---

## Delivery Surface

The first bootstrap may use Blob static website hosting for simplicity.

Azure Static Web Apps can be introduced later if deployment workflow and routing needs justify it.
