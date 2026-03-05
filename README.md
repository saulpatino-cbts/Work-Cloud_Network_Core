# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml)

A professional delivery platform for cloud network assessments across AWS and Azure.
Produces architecture diagrams, security findings, and executive-ready reports delivered
through a time-limited, password-protected client portal.

> **All six phases complete.** Platform is production-ready.

---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | ✅ Complete | 2026-03-05 |
| D | AI Analysis Engine | ✅ Complete | 2026-03-05 |
| E | Report Generation | ✅ Complete | 2026-03-05 |
| F | Delivery Portal | ✅ Complete | 2026-03-05 |

Critique-and-close records (every phase):
[`TODO_PhaseA.md`](TODO_PhaseA.md) ·
[`TODO_PhaseB.md`](TODO_PhaseB.md) ·
[`documentation/architecture/phase-c-discovery.md`](documentation/architecture/phase-c-discovery.md) ·
[`TODO_PhaseD.md`](TODO_PhaseD.md) ·
[`TODO_PhaseE.md`](TODO_PhaseE.md) ·
[`TODO_PhaseF.md`](TODO_PhaseF.md)

Architecture docs:
[Phase C](documentation/architecture/phase-c-discovery.md) ·
[Phase D](documentation/architecture/phase-d-analysis.md) ·
[Phase E](documentation/architecture/phase-e-reports.md) ·
[Phase F](documentation/architecture/phase-f-portal.md)

---

## What It Produces

For each engagement, the platform generates and delivers:

| Output | Format | Phase |
|---|---|---|
| Network topology diagrams | `.drawio`, `.svg` (Mermaid), `.png` | B |
| Topology models | Pydantic v2 JSON checkpoints | C |
| Findings report | Observed-state, framework-mapped | D |
| Executive report | PDF (WeasyPrint) | E |
| Technical report | PDF (full finding detail) | E |
| Presentation deck | PPTX (10 sections) | E |
| HTML preview | Self-contained, no PDF toolchain | E |
| Regional reports | EN + JA PDF (JA gate enforced) | E |
| Client delivery portal | Static HTML on S3 / Azure Blob | F |

---

## Full Engagement Workflow

```
cna init             → Engagement folder, welcome packet, env form, permission guide
     │
cna discover aws     → AWSTopology checkpoint (STS AssumeRole, all org accounts)
cna discover azure   → AzureTopology checkpoint (DefaultAzureCredential, all subscriptions)
     │
cna diagram generate → .drawio + Mermaid + PNG (three formats)
     │
cna analyze          → FindingsReport (11 AWS + 7 Azure rules, MCP enrichment)
     │
cna report preview   → HTML preview for pre-review inspection
cna review complete  → review_complete=True stamped in store
cna report generate  → Executive PDF + Technical PDF + PPTX + Regional EN/JA
     │
cna publish run      → S3 or Azure Blob upload, pre-signed portal URL → client
cna publish status   → Check portal liveness and TTL remaining
```

---

## Quick Start

### Prerequisites

```bash
# Python 3.12+
pip install -e .[dev]

# For full diagram export
docker-compose up

# Pre-commit hooks
pre-commit install && pre-commit run --all-files
```

### Initialize

```bash
cna init --client acme --platform aws --platform azure
# Creates: ./engagements/acme-20260305-a3f2/
```

### Discover

```bash
cna discover aws \
  --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly

cna discover azure \
  --engagement-id acme-20260305-a3f2 \
  --tenant-id 00000000-0000-0000-0000-000000000000
```

### Analyze

```bash
cna analyze --engagement-id acme-20260305-a3f2 --aws --azure
```

### Generate Reports

```bash
cna report preview  --engagement-id acme-20260305-a3f2
cna review complete --engagement-id acme-20260305-a3f2
cna report generate --engagement-id acme-20260305-a3f2
cna report generate --engagement-id acme-20260305-a3f2 --skip-pdf   # HTML only
cna report generate --engagement-id acme-20260305-a3f2 --regional-ja --ja-review-complete
```

### Publish to Client

```bash
# AWS S3
cna publish run \
  --engagement-id acme-20260305-a3f2 \
  --cloud aws \
  --bucket cna-deliverables-prod

# Azure Blob
cna publish run \
  --engagement-id acme-20260305-a3f2 \
  --cloud azure \
  --storage-account cnadeliveries \
  --container acme-20260305-a3f2

# Check status
cna publish status --engagement-id acme-20260305-a3f2
```

---

## Architecture

```
cna/
├── cli/
│   ├── discover.py          # cna discover aws / azure
│   ├── diagram.py           # cna diagram generate / preview
│   ├── analyze.py           # cna analyze
│   ├── report.py            # cna report generate / preview
│   └── publish.py           # cna publish run / status
├── core/
│   ├── topology_schema.py   # v1.1.0 AWS + Azure Pydantic models
│   ├── findings_schema.py   # Findings: observed_state + severity + frameworks
│   ├── persistence.py       # EngagementStore — atomic writes, audit log
│   ├── auth.py              # STS AssumeRole + DefaultAzureCredential
│   └── escalation_engine.py # DD-016: CRITICAL finding alert handler
├── diagram_engine/        # Phase B — .drawio, Mermaid, PNG
├── modules/               # Phase C — AWS + Azure discovery
├── ai_engine/             # Phase D — 11 AWS + 7 Azure rules, MCP, hedge detection
├── report_engine/         # Phase E — PDF, PPTX, HTML, regional EN/JA
└── delivery_portal/       # Phase F — S3 + Azure Blob, portal, retention
    ├── portal_generator.py  # Static HTML portal + staleness badges
    ├── s3_deployer.py       # S3 upload + CORS + pre-signed URLs
    ├── azure_blob_deployer.py # Azure Blob + SAS tokens + DefaultAzureCredential
    ├── access_manager.py    # TTL enforcement, expiry checks, audit record
    └── retention_engine.py  # DD-019: 90-day retention enforcement
documentation/
├── architecture/          # Phase C, D, E, F architecture docs
├── design/                # DD-001 through DD-019
├── policies/              # Data handling, LZ scope, JA translation protocol
├── client-packet/         # Welcome packet, env form, permission guide
└── development/           # Module guide, diagram generation, branching
```

---

## Design Contracts (All Enforced in Code)

| DD | Contract | Enforced In |
|---|---|---|
| DD-002 | `observed_state` = fact only, 16 hedge patterns blocked | `ObservedStateEnforcer` |
| DD-003 | Findings and recommendations are separate code paths | `AnalysisEngine` vs `RecommendationEngine` |
| DD-005/016 | Blocked accounts/regions logged, never silently skipped | Discovery + `EscalationEngine` |
| DD-008 | AI engine reads from store only, never touches client env | `AnalysisEngine` |
| DD-009 | `review_complete=True` required before any PDF render | `RenderPipeline._enforce_review_gate()` |
| DD-013 | Deliverable staleness detection via SHA-256 checksum | `DeliverableManifest` + `PortalGenerator` |
| DD-015 | JA reports require native speaker sign-off | `RenderPipeline._enforce_ja_gate()` |
| DD-017 | Output files ISO-timestamp-stamped | `RenderPipeline._filename()` |
| DD-019 | 90-day retention: no re-publish after expiry | `RetentionEngine.check()` |

---

## Finding Catalog (Phase D)

### AWS (11 rules)

| Rule ID | Title | Severity |
|---|---|---|
| AWS-NET-001 | Default VPC exists | MEDIUM |
| AWS-NET-002 | VPC flow logs disabled | HIGH |
| AWS-NET-003 | SG unrestricted SSH | CRITICAL |
| AWS-NET-004 | SG unrestricted RDP | CRITICAL |
| AWS-NET-005 | SG all-traffic from internet | CRITICAL |
| AWS-NET-006 | TGW default route table association | MEDIUM |
| AWS-NET-007 | TGW default route table propagation | MEDIUM |
| AWS-NET-008 | Single Direct Connect — no redundancy | MEDIUM |
| AWS-NET-009 | NAT Gateway single-AZ | MEDIUM |
| AWS-NET-010 | Subnet without NACL association | MEDIUM |
| AWS-NET-011 | IGW missing on public subnet route table | MEDIUM |

### Azure (7 rules)

| Rule ID | Title | Severity |
|---|---|---|
| AZ-NET-001 | VNet no DDoS protection | MEDIUM |
| AZ-NET-002 | Subnet without NSG | HIGH |
| AZ-NET-003 | Azure Firewall Threat Intelligence not Deny | CRITICAL |
| AZ-NET-004 | Single ExpressRoute — no redundancy | MEDIUM |
| AZ-NET-005 | VNet peering gateway transit misconfiguration | MEDIUM |
| AZ-NET-006 | VNet no flow logs | HIGH |
| AZ-NET-007 | Application Gateway WAF disabled | HIGH |

---

## Required IAM / RBAC

### AWS Discovery (`CNA-ReadOnly`)
See [`cna/modules/network/module.yaml`](cna/modules/network/module.yaml)

### AWS Publish (`CNA-Publish`)
`s3:PutObject`, `s3:PutBucketCors`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket`
See [`documentation/architecture/phase-f-portal.md`](documentation/architecture/phase-f-portal.md)

### Azure Discovery
**Reader** at root Management Group · **Management Group Reader** at tenant root

### Azure Publish
**Storage Blob Data Contributor** on storage account or container

---

## Security

- `detect-secrets` + `gitleaks` pre-commit hooks on every commit
- `gitleaks-action` in CI on every push and PR
- Credentials never written to disk — STS and Azure tokens are in-memory only
- Pre-signed URLs and SAS tokens never stored — `AccessManager` records metadata only
- Portal access links hard-capped at 7 days TTL
- Engagement data retained 90 days post-delivery, then permanently deleted (DD-019)
- See [`documentation/policies/data-handling-policy.md`](documentation/policies/data-handling-policy.md)

---

## Contributing

1. Branch from `develop` — never commit directly to `main`
2. Pre-commit hooks run on every `git commit`
3. CI: secret scan + lint + unit tests (80% coverage gate)
4. Architecture decisions go through design doc review before implementation
5. `/documentation` updated in the same PR as code changes

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
