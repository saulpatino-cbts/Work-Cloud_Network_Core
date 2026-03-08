# MCP Usage Model

> Version: 1.0.0 | Status: Draft | Date: 2026-03-05

This document defines how MCP servers are used in the CNA Platform.

---

## Two MCP Roles

MCP servers serve two distinct purposes in this platform.

| Role | Purpose | Example Servers |
|---|---|---|
| Build-time MCP | Supports infrastructure design, Terraform generation, cloud service selection, and IaC refinement | Terraform MCP, AWS MCP, Azure MCP |
| Run-time MCP | Supports analysis enrichment, recommendations, AI-assisted post-processing, and output refinement | AWS MCP, Azure MCP |

---

## Build-Time MCP Usage

Build-time MCP usage is used by the CNA Operator and development workflow to:

- generate and refine Terraform
- validate provider-specific resource choices
- improve AWS and Azure workload mappings
- support cloud-native IaC best practices

Build-time MCP usage never processes customer engagement data.

---

## Run-Time MCP Usage

Run-time MCP usage is invoked by the hosted CNA Platform to:

- enrich findings with vendor guidance
- assist post-processing and recommendation generation
- support provider-specific interpretation of assessment outputs
- improve final artifacts without replacing observed-state controls

Run-time MCP usage operates on CNA Platform processing outputs and must respect evidence-backed findings.

---

## Separation Rule

Build-time MCP and run-time MCP must remain logically separate.

- IaC generation workflows must not mix with customer assessment data workflows.
- Customer engagement data must not be used to build platform infrastructure.
- Recommendation and enrichment must remain separate from finding generation.

---

## Approved MCP Servers

| MCP Server | Primary Role | Secondary Role |
|---|---|---|
| Terraform MCP | Build-time IaC generation and Terraform-aware guidance | None |
| AWS MCP | Build-time AWS workload design | Run-time recommendation/enrichment |
| Azure MCP | Build-time Azure workload design | Run-time recommendation/enrichment |
