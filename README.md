# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml)

A professional delivery platform for cloud network assessments across AWS and Azure.
Produces architecture diagrams, security findings, and executive-ready reports for
enterprise clients. **Phase C (Discovery Engine) is complete.**

---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | ✅ Complete | 2026-03-05 |
| D | AI Analysis | 🔄 Next | — |
| E | Report Generation | ⏳ Planned | — |
| F | Delivery Portal | ⏳ Planned | — |

See [`TODO_PhaseA.md`](TODO_PhaseA.md), [`TODO_PhaseB.md`](TODO_PhaseB.md),
and [`documentation/architecture/phase-c-discovery.md`](documentation/architecture/phase-c-discovery.md)
for complete critique-and-close records for each completed phase.

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

### Discover AWS (Phase C — available now)

```bash
# Full org discovery via STS AssumeRole
cna discover aws \
  --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly

# Specific accounts + regions
cna discover aws \
  --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly \
  --accounts 234567890123,345678901234 \
  --regions us-east-1,eu-west-1

# Resume interrupted run
cna discover aws \
  --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly \
  --resume
```

### Discover Azure (Phase C — available now)

```bash
# DefaultAzureCredential (az login / managed identity / env vars)
cna discover azure \
  --engagement-id acme-20260305-a3f2 \
  --tenant-id 00000000-0000-0000-0000-000000000000

# Service principal
cna discover azure \
  --engagement-id acme-20260305-a3f2 \
  --tenant-id 00000000-0000-0000-0000-000000000000 \
  --client-id <app-id> \
  --client-secret <secret>

# Specific subscriptions + resume
cna discover azure \
  --engagement-id acme-20260305-a3f2 \
  --tenant-id 00000000-0000-0000-0000-000000000000 \
  --subscriptions sub-id-1,sub-id-2 \
  --resume
```

### Generate Diagrams (Phase B — available now)

```bash
# With draw.io CLI + Mermaid CLI (Docker recommended)
docker-compose run cna cna diagram generate --engagement-id acme-20260305-a3f2

# XML-only mode (no external tools required)
CNA_SKIP_RASTER=true cna diagram generate --engagement-id acme-20260305-a3f2
```

---

## Architecture

```
cna/
├── cli/              # Click CLI entry points (all phases)
│   ├── discover.py             # cna discover aws / cna discover azure
│   └── diagram.py              # cna diagram generate / preview
├── core/             # Data contracts, auth, persistence, logging, exceptions
│   ├── topology_schema.py      # v1.1.0 — AWS + Azure Pydantic models
│   ├── findings_schema.py      # Findings with observed_state enforcement
│   ├── persistence.py          # EngagementStore — atomic writes, audit log
│   ├── auth.py                 # STS AssumeRole, DefaultAzureCredential, Key Vault
│   └── observed_state_validator.py  # 16 hedge patterns + evidence linkage
├── diagram_engine/   # Phase B — three output formats
│   ├── drawio_generator.py     # draw.io XML (VPC, VNet, TGW, vWAN)
│   ├── mermaid_generator.py    # Mermaid text (org hierarchy, LZ, module deps)
│   ├── diagrams_generator.py   # Mingrammer PNG (AWS + Azure, graceful fallback)
│   ├── export_pipeline.py      # .drawio → .svg → .png → .pdf
│   └── naming.py               # Canonical diagram filename convention
├── modules/          # Pluggable assessment modules
│   ├── network/discovery/
│   │   ├── aws_discovery.py    # STS + EC2/TGW/DX paginators, checkpoint resume
│   │   └── azure_discovery.py  # ARM REST + Resource Graph, MG hierarchy
│   └── security/               # Phase C target (next)
├── ai_engine/        # Phase D — MCP-connected analysis (stub)
├── report_engine/    # Phase E — Jinja2 templates, PPTX (stub)
└── delivery_portal/  # Phase F — static portal (stub)
documentation/
├── architecture/     # System overview, repo structure, Phase C discovery design
├── design/           # All design decisions (DD-001 through DD-016)
├── policies/         # Data handling, LZ scope, JA translation protocol
├── client-packet/    # Welcome packet, env form, permission guide, engagement model
└── development/      # Module guide, diagram generation, branching strategy
```

---

## Topology Schema (v1.1.0)

**AWS models:** VPC, Subnet, SecurityGroup, NACL, RouteTable, IGW, NAT Gateway,
VPC Peering, TGW + Attachments, VPN Gateway, Direct Connect, Network Firewall Policy

**Azure models:** VNet, Subnet (with NSG/delegation/service endpoints), Route Table,
VNet Peering, Azure Firewall (with Policy + Threat Intel), Application Gateway (WAF),
vWAN + Hub (with routing state), Private DNS Zone (with VNet links),
ExpressRoute Circuit, Management Group hierarchy

All models are Pydantic v2, version-pinned at `TOPOLOGY_SCHEMA_VERSION = "1.1.0"`.
Schema version mismatch between a checkpoint and the current engine is a hard failure —
re-discovery required.

---

## Discovery Coverage (Phase C)

| Cloud | Scope | Blocked Handling | Resume |
|---|---|---|---|
| AWS | All org accounts × all enabled regions | `discovery_blocked=True` + reason logged + audit event | Per account+region checkpoint |
| Azure | All tenant subscriptions × all resource groups | `discovery_blocked=True` + HTTP status + reason logged | Per subscription checkpoint |

### AWS API Coverage (per account per region)
`ec2`: VPCs, Subnets, Route Tables, IGWs, NAT GWs, SGs, NACLs, VPC Peering,
VPN Gateways, TGWs, TGW Attachments · `directconnect`: Connections, Virtual Interfaces ·
`organizations`: account list (management account) · `sts`: AssumeRole

### Azure API Coverage (per subscription)
ARM: VNets, Subnets, Peerings, vWAN + Hubs, Azure Firewalls, App Gateways,
Private DNS Zones + VNet Links, ExpressRoute Circuits · Management API: MG hierarchy

---

## Required IAM / RBAC

### AWS
- Role `CNA-ReadOnly` must exist in every member account with trust to management account
- See `cna/modules/network/module.yaml` for the full IAM permission list
- See `documentation/client-packet/permission-grant-guide.md` for the client-facing template

### Azure
- **Reader** at root Management Group (inherits to all subscriptions)
- **Management Group Reader** at tenant root (for MG hierarchy)
- For Private DNS: Reader at subscription level is sufficient
- `Network Contributor` is **not** required — all operations are read-only

---

## Design Decisions

All 16 architectural decisions are documented in
[`documentation/design/design-decisions.md`](documentation/design/design-decisions.md).

Key decisions:
- **DD-002:** `observed_state` enforced as observed fact only — hedge language
  detection + evidence linkage check block assumption-based findings
- **DD-005/DD-016:** Every blocked account/region/subscription is logged with
  reason, HTTP status, and account ID — never silently skipped
- **DD-009:** Human review gate blocks report generation — `ReviewGateError` in
  report engine, `review_complete` flag required in engagement state
- **DD-011:** Landing zone = Mermaid/draw.io docs, **not IaC**
- **DD-015:** JA reports require native speaker review gate before delivery

---

## Security

- `detect-secrets` + `gitleaks` pre-commit hooks on every commit
- `gitleaks-action` in CI on every push and PR
- Credentials are **never** written to disk — STS tokens and Azure tokens are in-memory only
- `--client-secret` flag is in-memory only: never logged, never persisted
- Engagement data retained 90 days post-delivery, then permanently deleted
- See [`documentation/policies/data-handling-policy.md`](documentation/policies/data-handling-policy.md)

---

## Phase D — What's Next

Phase D connects the topology models produced in Phase C to the AI analysis engine:

- `cna analyze` — loads `AWSTopology` / `AzureTopology` checkpoints, runs finding generation
- MCP router connects to `awslabs/mcp` (AWS) and Microsoft Azure MCP Server (Azure)
- `recommendation_engine.py` strictly separated from `analysis_engine.py` — vendor
  recommendations never mixed with observed findings (DD-002)
- Every finding: `observed_state` required, `framework_mappings` required,
  hedge language detection blocks publication
- Output: versioned `FindingsReport` written to `EngagementStore`

---

## Contributing

1. Branch from `develop` — never commit directly to `main`
2. Pre-commit hooks run automatically on `git commit`
3. CI requires: secret scan + lint (no `|| true`) + unit tests (80% coverage gate)
4. All architecture decisions go through design doc review before implementation
5. Documentation in `/documentation` is updated in the same PR as code changes

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
