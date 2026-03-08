# 01 — Platform Foundation

> Version: 1.0.0 | Status: Draft | Date: 2026-03-05
>
> This document defines the first workstream for the hosted CNA Platform.

---

## Objective

`01-platform-foundation` establishes the hosted CNA Platform as the compute-operated assessment system that ingests client data, processes assessment workloads, uses AI-assisted post-processing, and produces deliverables for customer consumption.

This workstream replaces the older workstation-first mental model with a hosted platform model.

---

## Core Terms

| Term | Meaning |
|---|---|
| **CNA Platform** | The compute-hosted assessment system operated by the CNA Operator; ingests, processes, analyzes, diagrams, and produces reports |
| **CNA Operator** | The cloud architect running and supervising the assessment workflow |
| **CNA-Client Connector** | The customer-side configuration, permissions, scripts, or lightweight integration that supplies data to the CNA Platform |
| **Client Cloud Environment** | The customer’s AWS accounts, AWS Organization, Azure subscriptions, or Azure tenant being assessed |
| **Assessment Artifacts** | Raw discovery payloads, normalized topology data, findings, diagrams, reports, decks, and portal outputs |

---

## Workstream Scope

This workstream covers only CNA Platform workloads.

Included:
- Hosted ingress for uploads and API connections
- Assessment artifact storage
- Processing and orchestration workloads
- AI integration model
- Static delivery and visualization surface
- Secrets, identity, and observability foundations
- Terraform layout for AWS and Azure deployments

Excluded from this workstream:
- Detailed client connector implementation per cloud
- Final rule catalogs for all analysis modules
- Full customer portal UX design
- Commercial packaging / multi-tenant billing model

---

## Target Architecture

```text
CNA-Client Connector
    └── manual upload and/or API connection
            └── CNA Platform ingress
                    └── raw artifact storage
                            └── processing and orchestration
                                    └── AI-assisted post-processing
                                            └── reports, diagrams, decks, static website
```

The CNA Platform is the system of processing and record. The client environment remains external to the platform boundary.

---

## Build Outputs

This workstream must produce:

1. Hosted platform workload definition
2. Cloud mapping for Azure and AWS
3. Terraform structure and module boundaries
4. MCP usage model for build-time and run-time usage
5. Repo structure updates for infrastructure as code

---

## Exit Criteria

`01-platform-foundation` is complete when:

- CNA Platform workloads are documented
- AWS and Azure target mappings are documented
- Terraform skeleton exists in-repo
- MCP usage is split into build-time and run-time responsibilities
- Repo structure reflects hosted platform deployment assets
