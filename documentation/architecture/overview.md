# CNA Platform — Architecture Overview

> Version: 1.1.0 | Date: 2026-03-05

The CNA (Cloud Network Assessment) platform is a CLI-driven assessment tool that discovers, analyzes, diagrams, and delivers a structured security and architecture assessment of a client's cloud network topology. It operates entirely from the operator's workstation and produces client-ready PDF and PPTX reports.

---

## Core Architecture

The platform is organized around five engines that execute sequentially. Each engine reads from and writes to the `EngagementStore` — a local, versioned, engagement-scoped data store.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Discovery  │───►│   Diagram    │───►│  AI Analysis │───►│   Report     │───►│  Delivery    │
│   Engine     │    │   Engine     │    │   Engine     │    │  Generation  │    │   Portal     │
│              │    │              │    │              │    │              │    │              │
│ AWS multi-   │    │ draw.io      │    │ Finding      │    │ PDF + PPTX   │    │ S3 / Blob    │
│ acct + Azure │    │ Mermaid      │    │ rules engine │    │ Jinja2       │    │ Pre-signed   │
│ multi-sub    │    │ PNG export   │    │ MCP recs     │    │ Review gate  │    │ URL / SAS    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
        │                  │                  │                  │                  │
        └──────────────────┴──────────────────┴──────────────────┴──────────────────┘
                                        EngagementStore
                               engagements/{id}/ (local filesystem)
```

---

## The Three Guarantees

1. **Observed state only** — Every finding is backed by evidence collected during discovery. No hedged language (`likely`, `probably`, `appears to`) is permitted. Enforced by `ObservedStateEnforcer` before any finding is persisted.

2. **Human review gate** — No report reaches a client until an operator sets `review_complete=True`, which is logged with operator identity and timestamp. Enforced by `ReviewGateError` in the report engine.

3. **Recommendations from vendors only** — Remediation guidance is sourced exclusively from AWS MCP Server and Azure MCP Server. The analysis engine writes findings; the recommendation engine writes recommendations. They share no code path.

---

## Architecture Documents

| Document | Covers |
|---|---|
| [`deployment-map.md`](deployment-map.md) | What is deployed, what is pending, CNA vs CNA-client boundary, remote connection map |
| [`discovery-engine.md`](discovery-engine.md) | AWS + Azure discovery flows, IAM/RBAC requirements, checkpoint format, resume behavior |
| [`ai-analysis-engine.md`](ai-analysis-engine.md) | Finding rules (AWS + Azure), MCP recommendation engine, CLI entry point |
| [`report-generation.md`](report-generation.md) | Review gate, output deliverables, template structure, JA translation protocol |
| [`delivery-portal.md`](delivery-portal.md) | Publish flow, S3/Blob storage targets, retention, CD pipeline integration |
| [`repo-structure.md`](repo-structure.md) | Full directory tree with descriptions |
