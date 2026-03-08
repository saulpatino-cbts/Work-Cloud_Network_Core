# Platform Workloads

> Version: 1.0.0 | Status: Draft | Date: 2026-03-05

This document defines the hosted workloads used by the CNA Platform.

---

## Workload Inventory

| Workload | Responsibility | Notes |
|---|---|---|
| Ingress Service | Accept manual uploads, API submissions, and connector callbacks | Supports authenticated upload and API-triggered assessment intake |
| Raw Artifact Storage | Store incoming files, payloads, and source exports | Immutable source of raw assessment evidence |
| Normalization Service | Convert raw payloads into normalized topology and assessment models | Bridges client data formats to CNA internal schemas |
| Processing Workers | Run discovery ingestion, validation, analysis, diagram generation, and report rendering | Containerized async job runners |
| Orchestration Layer | Queue, schedule, and coordinate workload stages | Decouples ingestion from processing |
| Metadata Store | Track engagements, jobs, artifacts, statuses, timestamps, and ownership | Control-plane source of truth |
| AI Integration Layer | Invoke Azure OpenAI and AWS equivalent services for enrichment and post-processing | Abstracted provider interface |
| Visualization and Delivery Site | Publish static web outputs, diagrams, and downloadable deliverables | Customer-facing surface |
| Secrets and Identity Layer | Handle service auth, secrets retrieval, and provider identity | Build and runtime separation required |
| Observability Layer | Collect logs, metrics, traces, and audit events | Required for operator trust and troubleshooting |

---

## Processing Sequence

```text
Ingress
  -> raw artifact storage
  -> normalization
  -> orchestration queue
  -> processing workers
  -> AI-assisted enrichment/post-processing
  -> diagrams/reports/decks/static website assets
  -> delivery surface
```

---

## Platform Boundaries

The CNA Platform owns ingress, storage, compute, AI integration, and output generation.

The CNA-Client Connector does not run the platform. It only supplies data and access paths into the CNA Platform.

---

## Design Principles

- Raw artifacts are preserved before transformation.
- Processing is asynchronous and replayable.
- AI-assisted steps are additive and auditable.
- Deliverables are generated from stored artifacts, not ad hoc manual assembly.
- Static presentation outputs are generated from controlled platform state.
