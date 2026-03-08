# 06 — Azure AI and Observability Bootstrap

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the Azure AI and observability slice for the hosted CNA Platform.

---

## Objective

`06-azure-ai-and-observability-bootstrap` adds the first Azure-native AI and application telemetry foundation for the hosted CNA Platform.

---

## Delivered Module

| Module | Responsibility |
|---|---|
| `providers/azure/ai` | Azure OpenAI account foundation and Application Insights telemetry |

---

## Platform Role

This slice provides:
- Azure-native AI service foundation for CNA post-processing and analysis workflows
- application telemetry foundation for hosted CNA workloads
- future wiring targets for `cna-api` and `cna-worker` runtime configuration

---

## First-Bootstrap Position

This workstream provisions the AI account and observability endpoint foundation.

A later workstream should add:
- model deployment configuration
- runtime app settings
- secret references and identity-based access wiring
- deeper monitoring and alerting rules
