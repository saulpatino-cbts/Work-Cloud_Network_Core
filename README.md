# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml)

A professional delivery platform for cloud network assessments across AWS and Azure.
Produces architecture diagrams, security findings, and executive-ready reports for
enterprise clients. **Phase C (Discovery Engine) is in active development.**

---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | 🔄 In Progress | — |
| D | AI Analysis | ⏳ Planned | — |
| E | Report Generation | ⏳ Planned | — |
| F | Delivery Portal | ⏳ Planned | — |

See [`TODO_PhaseA.md`](TODO_PhaseA.md) and [`TODO_PhaseB.md`](TODO_PhaseB.md) for
complete critique-and-close records for each completed phase.

---

## What It Produces

For each engagement, the platform generates:

- **Architecture diagrams** in three formats:
  - `.drawio` — editable by client, relationship-rich, exportable
  - `.svg` / Mermaid — portal-embedded, version-controlled, GitHub-renderable
  - `.png` — code-driven via Mingrammer `diagrams`, AWS/Azure icon fidelity
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

### Generate Diagrams (Phase B — available now)

```bash
# With draw.io CLI + Mermaid CLI (Docker recommended)
docker-compose run cna cna diagram generate --engagement-id acme-20260305-a3f2

# XML-only mode (no external tools required)
CNA_SKIP_RASTER=true cna diagram generate --engagement-id acme-20260305-a3f2

# Preview Mermaid diagram
cna diagram preview --type account-hierarchy
```

### Run Discovery (Phase C — in development)

```bash
# AWS (requires AssumeRole access)
cna discover aws --engagement-id acme-20260305-a3f2 --org-role arn:aws:iam::MGMT:role/CNA-ReadOnly

# Azure (requires Reader + Network Contributor at MG level)
cna discover azure --engagement-id acme-20260305-a3f2 --tenant-id <tenant-id>
```

---

## Architecture

```
cna/
├── cli/              # Click CLI entry points (all phases)
├── core/             # Data contracts, auth, persistence, logging, exceptions
│   ├── topology_schema.py      # v1.1.0 — AWS + Azure Pydantic models
│   ├── findings_schema.py      # Findings with observed_state enforcement
│   ├── persistence.py          # EngagementStore — atomic writes, audit log
│   ├── auth.py                 # STS AssumeRole, DefaultAzureCredential, Key Vault
│   └── observed_state_validator.py  # 16 hedge patterns + evidence linkage
├── diagram_engine/   # Phase B — three output formats
│   ├── drawio_generator.py     # draw.io XML (VPC, VNet, TGW, vWAN)
│   ├── mermaid_generator.py    # Mermaid text (org hierarchy, LZ, module deps)
│   ├── diagrams_generator.py   # Mingrammer PNG (AWS + Azure)
│   ├── export_pipeline.py      # .drawio → .svg → .png → .pdf
│   └── naming.py               # Canonical diagram filename convention
├── modules/          # Pluggable assessment modules (network, security, zerotrust...)
├── ai_engine/        # Phase D — MCP-connected analysis (stub)
├── report_engine/    # Phase E — Jinja2 templates, PPTX (stub)
└── delivery_portal/  # Phase F — static portal (stub)
documentation/
├── architecture/     # System overview, repo structure
├── design/           # All design decisions (DD-001 through DD-016)
├── policies/         # Data handling, LZ scope, JA translation protocol
├── client-packet/    # Welcome packet, env form, permission guide, engagement model
└── development/      # Module guide, diagram generation, branching strategy
```

---

## Topology Schema (v1.1.0)

**AWS models:** VPC, Subnet, SecurityGroup, NACL, RouteTable, IGW, NAT Gateway,
VPC Peering, TGW + Attachments, VPN Gateway, Direct Connect, Network Firewall Policy

**Azure models:** VNet, Subnet (with NSG/delegation), Route Table, VNet Peering,
Azure Firewall, Application Gateway, vWAN + Hub, Private DNS Zone, ExpressRoute Circuit,
Management Group hierarchy

All models are Pydantic v2, version-pinned at `TOPOLOGY_SCHEMA_VERSION = "1.1.0"`.

---

## Design Decisions

All 16 architectural decisions are documented in
[`documentation/design/design-decisions.md`](documentation/design/design-decisions.md).

Key decisions:
- **DD-002:** `observed_state` enforced as observed fact only — hedge language
  detection + evidence linkage check block assumption-based findings
- **DD-009:** Human review gate blocks report generation — `ReviewGateError` in
  report engine, `review_complete` flag required in engagement state
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

## Phase C — What's Next

Phase C implements the discovery engine:

- `cna discover aws` — STS AssumeRole, paginated EC2/VPC/TGW/DX API calls across all regions
- `cna discover azure` — DefaultAzureCredential, ARM REST + Resource Graph queries
- Output: `AWSTopology` / `AzureTopology` Pydantic models written to `EngagementStore`
- Blocked accounts/regions logged with reason — never silently skipped
- `--resume` flag restarts from last completed checkpoint per account

See `cna/modules/network/` and `cna/modules/security/` for Phase C targets.

---

## Contributing

1. Branch from `develop` — never commit directly to `main`
2. Pre-commit hooks run automatically on `git commit`
3. CI requires: secret scan + lint (no `|| true`) + unit tests (80% coverage gate)
4. All architecture decisions go through design doc review before implementation
5. Documentation in `/documentation` is updated in the same PR as code changes

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
