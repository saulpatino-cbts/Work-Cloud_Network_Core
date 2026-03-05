# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml)

A professional delivery platform for cloud network assessments across AWS and Azure.
Produces architecture diagrams, security findings, and executive-ready reports for
enterprise clients. **Phase E (Report Generation) is complete. Phase F (Delivery Portal) is active.**

---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | ✅ Complete | 2026-03-05 |
| D | AI Analysis Engine | ✅ Complete | 2026-03-05 |
| E | Report Generation | ✅ Complete | 2026-03-05 |
| F | Delivery Portal | 🔄 Active | — |

Critique-and-close records:
[`TODO_PhaseA.md`](TODO_PhaseA.md) · [`TODO_PhaseB.md`](TODO_PhaseB.md) ·
[`documentation/architecture/phase-c-discovery.md`](documentation/architecture/phase-c-discovery.md) ·
[`TODO_PhaseD.md`](TODO_PhaseD.md) · [`TODO_PhaseE.md`](TODO_PhaseE.md) ·
[`documentation/architecture/phase-d-analysis.md`](documentation/architecture/phase-d-analysis.md) ·
[`documentation/architecture/phase-e-reports.md`](documentation/architecture/phase-e-reports.md)

---

## What It Produces

For each engagement, the platform generates:

- **Architecture diagrams** in three formats:
  - `.drawio` — editable by client, relationship-rich, exportable
  - `.svg` / Mermaid — portal-embedded, version-controlled, GitHub-renderable
  - `.png` — code-driven via Mingrammer `diagrams`, AWS/Azure icon fidelity
- **Topology models** — `AWSTopology` and `AzureTopology` Pydantic v2 objects
  written as versioned checkpoints, consumed by every downstream phase
- **Findings report** — observed-state findings mapped to AWS Well-Architected,
  Azure WAF, NIST CSF, CIS Benchmarks, Zero Trust
- **Executive PDF** — C-suite ready, CRITICAL/HIGH finding highlights, top recommendations
- **Technical PDF** — full finding detail, evidence refs, framework mapping tables
- **Presentation deck** — 10-section PPTX (executive summary → remediation roadmap)
- **HTML preview** — self-contained, no PDF toolchain required, severity colour-coded
- **Regional reports** — EN and JA (JA requires native speaker review gate)

---

## Quick Start

### Prerequisites

```bash
# Python 3.12+
pip install -e .[dev]

# For full diagram export (draw.io CLI + Mermaid CLI)
docker-compose up

# Verify pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Initialize an Engagement

```bash
cna init --client acme --platform aws --platform azure
# Creates: ./engagements/acme-20260305-a3f2/
```

### Discover (Phase C — complete)

```bash
# AWS
cna discover aws \
  --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly

# Azure
cna discover azure \
  --engagement-id acme-20260305-a3f2 \
  --tenant-id 00000000-0000-0000-0000-000000000000
```

### Analyze (Phase D — complete)

```bash
cna analyze --engagement-id acme-20260305-a3f2 --aws --azure
cna analyze --engagement-id acme-20260305-a3f2 --aws --dry-run
cna analyze --engagement-id acme-20260305-a3f2 --aws --azure --no-recommendations
```

### Generate Reports (Phase E — complete)

```bash
# Inspect findings before review (no PDF toolchain required)
cna report preview --engagement-id acme-20260305-a3f2

# Sign off findings (required before cna report generate)
cna review complete --engagement-id acme-20260305-a3f2

# Full render: executive PDF + technical PDF + PPTX + HTML + regional EN
cna report generate --engagement-id acme-20260305-a3f2

# HTML only — no WeasyPrint required
cna report generate --engagement-id acme-20260305-a3f2 --skip-pdf

# Include JA regional report
cna report generate \
  --engagement-id acme-20260305-a3f2 \
  --regional-ja --ja-review-complete
```

### Generate Diagrams (Phase B — complete)

```bash
docker-compose run cna cna diagram generate --engagement-id acme-20260305-a3f2
```

---

## Architecture

```
cna/
├── cli/              # Click CLI entry points (all phases)
│   ├── discover.py             # cna discover aws / cna discover azure
│   ├── diagram.py              # cna diagram generate / preview
│   ├── analyze.py              # cna analyze
│   └── report.py               # cna report generate / cna report preview
├── core/             # Data contracts, auth, persistence, logging, exceptions
│   ├── topology_schema.py      # v1.1.0 — AWS + Azure Pydantic models
│   ├── findings_schema.py      # Findings with observed_state + severity + framework mappings
│   ├── persistence.py          # EngagementStore — atomic writes, audit log
│   ├── auth.py                 # STS AssumeRole, DefaultAzureCredential, Key Vault
│   └── escalation_engine.py    # DD-016: CRITICAL finding alert handler
├── diagram_engine/   # Phase B — COMPLETE
├── modules/          # Phase C — COMPLETE
├── ai_engine/        # Phase D — COMPLETE
│   ├── analysis_engine.py      # 11 AWS + 7 Azure rules, dedup, escalation
│   ├── observed_state_enforcer.py
│   ├── recommendation_engine.py
│   └── mcp_client/             # AWS + Azure MCP clients with graceful fallback
├── report_engine/    # Phase E — COMPLETE
│   ├── render_pipeline.py      # Orchestrator: review gate, all formats, manifest
│   ├── executive_report.py     # Executive PDF (Jinja2 → WeasyPrint)
│   ├── technical_report.py     # Full technical PDF
│   ├── presentation_deck.py    # 10-section PPTX (python-pptx)
│   ├── regional_report.py      # EN + JA regional PDFs (JA gate enforced)
│   ├── html_preview.py         # Self-contained HTML, no PDF toolchain
│   ├── deliverable_manifest.py # Manifest written to store for Phase F
│   └── templates/              # Jinja2 templates (html_preview, executive, technical, regional)
└── delivery_portal/  # Phase F — ACTIVE
documentation/
├── architecture/     # Phase C, D, E architecture docs
├── design/           # DD-001 through DD-016
├── policies/         # Data handling, LZ scope, JA translation protocol
├── client-packet/    # Welcome packet, env form, permission guide
└── development/      # Module guide, diagram generation, branching strategy
```

---

## Report Workflow

```
cna analyze          → FindingsReport (review_complete=False)
     │
cna report preview   → HTML preview for inspection (no gate check)
     │
cna review complete  → review_complete=True stamped in EngagementStore
     │
cna report generate  → Executive PDF + Technical PDF + PPTX + Regional
     │
cna publish          → Phase F portal upload (active)
```

---

## Design Contracts (All Enforced in Code)

| DD | Contract | Where Enforced |
|---|---|---|
| DD-002 | `observed_state` = fact only, 16 hedge patterns blocked | `ObservedStateEnforcer` in analysis engine |
| DD-003 | Findings and recommendations are separate code paths | `AnalysisEngine` vs `RecommendationEngine` |
| DD-005/016 | Blocked accounts/regions logged, never silently skipped | Discovery + escalation engine |
| DD-008 | AI engine reads from store only, never touches client env | `AnalysisEngine` reads checkpoints only |
| DD-009 | `review_complete=True` required before any PDF render | `RenderPipeline._enforce_review_gate()` |
| DD-013 | Deliverable staleness detection | `DeliverableManifest.checksum()` per record |
| DD-015 | JA reports require native speaker sign-off | `RenderPipeline._enforce_ja_gate()` + `RegionalReportRenderer` |
| DD-017 | Output files ISO-timestamp-stamped | `RenderPipeline._filename()` |

---

## Finding Catalog (Phase D)

### AWS Finding Rules (11)

| Rule ID | Title | Severity |
|---|---|---|
| AWS-NET-001 | Default VPC exists | MEDIUM |
| AWS-NET-002 | VPC flow logs disabled | HIGH |
| AWS-NET-003 | SG unrestricted SSH (port 22) | CRITICAL |
| AWS-NET-004 | SG unrestricted RDP (port 3389) | CRITICAL |
| AWS-NET-005 | SG all-traffic from internet | CRITICAL |
| AWS-NET-006 | TGW default route table association | MEDIUM |
| AWS-NET-007 | TGW default route table propagation | MEDIUM |
| AWS-NET-008 | Single Direct Connect — no redundancy | MEDIUM |
| AWS-NET-009 | NAT Gateway single-AZ | MEDIUM |
| AWS-NET-010 | Subnet without NACL association | MEDIUM |
| AWS-NET-011 | IGW missing on public subnet route table | MEDIUM |

### Azure Finding Rules (7)

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

## Topology Schema (v1.1.0)

**AWS:** VPC, Subnet, SG, NACL, RouteTable, IGW, NAT GW, VPC Peering,
TGW + Attachments, VPN Gateway, Direct Connect, Network Firewall Policy

**Azure:** VNet, Subnet, Route Table, VNet Peering, Azure Firewall, App Gateway (WAF),
vWAN + Hub, Private DNS Zone, ExpressRoute Circuit, Management Group hierarchy

All models are Pydantic v2 at `TOPOLOGY_SCHEMA_VERSION = "1.1.0"`.
Schema version mismatch is a hard failure — re-discovery required.

---

## Required IAM / RBAC

### AWS
- Role `CNA-ReadOnly` in every member account with trust to management account
- See [`cna/modules/network/module.yaml`](cna/modules/network/module.yaml) for full permission list
- See [`documentation/client-packet/permission-grant-guide.md`](documentation/client-packet/permission-grant-guide.md)

### Azure
- **Reader** at root Management Group (inherits to all subscriptions)
- **Management Group Reader** at tenant root
- `Network Contributor` **not** required — all operations are read-only

---

## Security

- `detect-secrets` + `gitleaks` pre-commit hooks on every commit
- `gitleaks-action` in CI on every push and PR
- Credentials never written to disk — STS and Azure tokens are in-memory only
- Engagement data retained 90 days post-delivery, then permanently deleted
- See [`documentation/policies/data-handling-policy.md`](documentation/policies/data-handling-policy.md)

---

## Phase F — What’s Next (Delivery Portal)

Phase F reads `DeliverableManifest` from `EngagementStore` and produces a
static delivery portal per engagement:

- `cna publish` — builds static site, uploads to S3/Azure Blob
- Download inventory: every deliverable listed with format, lang, size, render date
- Staleness badges: any deliverable rendered before the last topology change is flagged
- Password-protected client link (pre-signed S3 URL or Azure SAS)
- Retention enforcement: automatic expiry at 90-day mark (DD-019)

---

## Contributing

1. Branch from `develop` — never commit directly to `main`
2. Pre-commit hooks run automatically on `git commit`
3. CI requires: secret scan + lint + unit tests (80% coverage gate)
4. All architecture decisions go through design doc review before implementation
5. `/documentation` updated in the same PR as code changes

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
