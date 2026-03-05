# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml)

A professional delivery platform for cloud network assessments across AWS and Azure.
Produces architecture diagrams, security findings, and executive-ready reports for
enterprise clients. **Phase D (AI Analysis Engine) is complete. Phase E (Report Generation) is active.**

---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | ✅ Complete | 2026-03-05 |
| D | AI Analysis Engine | ✅ Complete | 2026-03-05 |
| E | Report Generation | 🔄 Active | — |
| F | Delivery Portal | ⏳ Planned | — |

Critique-and-close records:
[`TODO_PhaseA.md`](TODO_PhaseA.md) · [`TODO_PhaseB.md`](TODO_PhaseB.md) ·
[`documentation/architecture/phase-c-discovery.md`](documentation/architecture/phase-c-discovery.md) ·
[`TODO_PhaseD.md`](TODO_PhaseD.md) · [`documentation/architecture/phase-d-analysis.md`](documentation/architecture/phase-d-analysis.md)

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
- **Executive deck** — PPTX with 10-section reviewed structure (not AI-improvised)
- **Regional reports** — EN and JA (with native speaker review gate)

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
# Generates: welcome packet, env info form, permission grant guide
```

### Discover (Phase C — complete)

```bash
# AWS: full org discovery via STS AssumeRole
cna discover aws \
  --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly

# Azure: DefaultAzureCredential (az login / managed identity / env vars)
cna discover azure \
  --engagement-id acme-20260305-a3f2 \
  --tenant-id 00000000-0000-0000-0000-000000000000
```

### Analyze (Phase D — complete)

```bash
# Full analysis: AWS + Azure finding rules, MCP enrichment
cna analyze \
  --engagement-id acme-20260305-a3f2 \
  --aws --azure

# Dry run (findings generated, not written)
cna analyze \
  --engagement-id acme-20260305-a3f2 \
  --aws --dry-run

# Air-gapped / offline (no MCP, offline recommendation fallback)
cna analyze \
  --engagement-id acme-20260305-a3f2 \
  --aws --azure --no-recommendations

# Mark findings reviewed (required before cna report)
cna review complete --engagement-id acme-20260305-a3f2
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
│   └── analyze.py              # cna analyze (Phase D)
├── core/             # Data contracts, auth, persistence, logging, exceptions
│   ├── topology_schema.py      # v1.1.0 — AWS + Azure Pydantic models
│   ├── findings_schema.py      # Findings with observed_state + severity + framework mappings
│   ├── persistence.py          # EngagementStore — atomic writes, audit log
│   ├── auth.py                 # STS AssumeRole, DefaultAzureCredential, Key Vault
│   └── escalation_engine.py    # DD-016: CRITICAL finding alert handler
├── diagram_engine/   # Phase B — three output formats
│   ├── drawio_generator.py     # draw.io XML (VPC, VNet, TGW, vWAN)
│   ├── mermaid_generator.py    # Mermaid text (org hierarchy, LZ, module deps)
│   ├── diagrams_generator.py   # Mingrammer PNG (AWS + Azure, graceful fallback)
│   └── export_pipeline.py      # .drawio → .svg → .png → .pdf
├── modules/          # Pluggable assessment modules
│   ├── network/discovery/
│   │   ├── aws_discovery.py    # STS + EC2/TGW/DX paginators, checkpoint resume
│   │   └── azure_discovery.py  # ARM REST + Resource Graph, MG hierarchy
│   └── security/               # Planned
├── ai_engine/        # Phase D — COMPLETE
│   ├── analysis_engine.py      # 11 AWS + 7 Azure finding rules, dedup, escalation
│   ├── observed_state_enforcer.py  # 16 hedge patterns block assumption language
│   ├── recommendation_engine.py    # MCP enrichment + offline fallback (DD-003)
│   └── mcp_client/
│       ├── mcp_router.py           # AWS / Azure routing
│       ├── aws_mcp_client.py       # awslabs/mcp — graceful degradation
│       └── azure_mcp_client.py     # Azure/azure-mcp — graceful degradation
├── report_engine/    # Phase E — ACTIVE
└── delivery_portal/  # Phase F — Planned
documentation/
├── architecture/     # System overview, Phase C discovery, Phase D analysis
├── design/           # All design decisions (DD-001 through DD-016)
├── policies/         # Data handling, LZ scope, JA translation protocol
├── client-packet/    # Welcome packet, env form, permission guide, engagement model
└── development/      # Module guide, diagram generation, branching strategy
```

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

All findings enforce: `observed_state` (fact, no hedge language) + `severity` +
`framework_mappings` (AWS WAF / Azure WAF / NIST CSF / CIS Benchmarks).

---

## Topology Schema (v1.1.0)

**AWS models:** VPC, Subnet, SecurityGroup, NACL, RouteTable, IGW, NAT Gateway,
VPC Peering, TGW + Attachments, VPN Gateway, Direct Connect, Network Firewall Policy

**Azure models:** VNet, Subnet (with NSG/delegation/service endpoints), Route Table,
VNet Peering, Azure Firewall (with Policy + Threat Intel), Application Gateway (WAF),
vWAN + Hub, Private DNS Zone, ExpressRoute Circuit, Management Group hierarchy

All models are Pydantic v2, version-pinned at `TOPOLOGY_SCHEMA_VERSION = "1.1.0"`.
Schema version mismatch between a checkpoint and the current engine is a hard failure —
re-discovery required.

---

## Discovery Coverage (Phase C)

| Cloud | Scope | Blocked Handling | Resume |
|---|---|---|---|
| AWS | All org accounts × all enabled regions | `discovery_blocked=True` + reason logged + audit event | Per account+region checkpoint |
| Azure | All tenant subscriptions × all resource groups | `discovery_blocked=True` + HTTP status + reason logged | Per subscription checkpoint |

### AWS API Coverage
`ec2`: VPCs, Subnets, Route Tables, IGWs, NAT GWs, SGs, NACLs, VPC Peering,
VPN Gateways, TGWs, TGW Attachments · `directconnect`: Connections, Virtual Interfaces ·
`organizations`: account list · `sts`: AssumeRole

### Azure API Coverage
ARM: VNets, Subnets, Peerings, vWAN + Hubs, Azure Firewalls, App Gateways,
Private DNS Zones + VNet Links, ExpressRoute Circuits · Management API: MG hierarchy

---

## Required IAM / RBAC

### AWS
- Role `CNA-ReadOnly` in every member account with trust to management account
- See `cna/modules/network/module.yaml` for full IAM permission list
- See `documentation/client-packet/permission-grant-guide.md` for client-facing template

### Azure
- **Reader** at root Management Group (inherits to all subscriptions)
- **Management Group Reader** at tenant root
- `Network Contributor` is **not** required — all operations are read-only

---

## Design Decisions

All 16 architectural decisions are documented in
[`documentation/design/design-decisions.md`](documentation/design/design-decisions.md).

Key decisions:
- **DD-002:** `observed_state` enforced as observed fact only — hedge language
  detection + evidence linkage check block assumption-based findings
- **DD-003:** Findings and recommendations are strictly separate code paths —
  `AnalysisEngine` generates findings; `RecommendationEngine` injects vendor MCP recommendations
- **DD-005/DD-016:** Every blocked account/region/subscription logged with reason and
  HTTP status — never silently skipped
- **DD-008:** AI analysis engine reads from our data store only — never touches client environment
- **DD-009:** Human review gate blocks report generation — `review_complete` flag required
- **DD-011:** Landing zone = Mermaid/draw.io docs, **not IaC**
- **DD-015:** JA reports require native speaker review gate before delivery

---

## Security

- `detect-secrets` + `gitleaks` pre-commit hooks on every commit
- `gitleaks-action` in CI on every push and PR
- Credentials are **never** written to disk — STS tokens and Azure tokens are in-memory only
- Engagement data retained 90 days post-delivery, then permanently deleted
- See [`documentation/policies/data-handling-policy.md`](documentation/policies/data-handling-policy.md)

---

## Phase E — What's Next (Report Generation)

Phase E consumes `FindingsReport` from `EngagementStore` and produces:

- **Executive PDF** — Jinja2-rendered, `reviewed_complete=True` gate enforced (DD-009)
- **PPTX deck** — 10-section structure: executive summary, scope, methodology,
  findings by severity, architecture diagrams, recommendations, roadmap
- **Regional EN/JA reports** — JA requires native speaker review gate (DD-015)
- **`cna report`** CLI — renders all formats in one command
- **`cna report preview`** — HTML preview without full PDF render

---

## Contributing

1. Branch from `develop` — never commit directly to `main`
2. Pre-commit hooks run automatically on `git commit`
3. CI requires: secret scan + lint + unit tests (80% coverage gate)
4. All architecture decisions go through design doc review before implementation
5. Documentation in `/documentation` updated in the same PR as code changes

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
