# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/ci.yml)
[![Release](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/release.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/release.yml)

A professional delivery platform for cloud network assessments across AWS and Azure.
Produces architecture diagrams, security findings, and executive-ready reports delivered
through a time-limited, password-protected client portal.

> **All six phases complete. Azure delivery hardening is now threshold-enforced, promotion-aware, and renewal-aware. AWS implementation track begins next.**

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
| — | CI/CD + IaC Hardening | ✅ Complete | 2026-03-06 |
| — | Azure Operational Hardening | ✅ Complete | 2026-03-06 |
| — | AWS Provider Expansion | ⏳ Next | — |

---

## Current Delivery State

The Azure delivery path now includes:
- direct Azure Monitor and Application Insights verification queries
- explicit threshold-based pass/fail gating for health and telemetry
- Front Door promotion actions with progressive origin-weight control intent
- certificate expiry-window enforcement with renewal-aware verification
- release manifest evidence summaries for health, telemetry, rollout, and certificate state

AWS platform parity is planned as the next implementation track.

---

## Quick Start

### 1. Prerequisites

```bash
# Python 3.11 or 3.12
pip install -e .[dev]

# Pre-commit hooks (runs gitleaks + ruff on every commit)
pre-commit install
pre-commit run --all-files

# Copy and fill environment file
cp .env.example .env
# Edit .env — see documentation/deployment-guide.md for every variable explained

# For full diagram export (draw.io CLI + Mermaid CLI)
docker-compose up
```

### 2. Single-Cloud Test (Recommended First Run)

You do not need both clouds configured. Run one at a time:

```bash
# --- Azure only ---
cna init --client contoso --platform azure
cna discover azure --engagement-id contoso-20260305-b1c3 --tenant-id <TENANT_ID>
cna analyze --engagement-id contoso-20260305-b1c3 --azure
cna report preview --engagement-id contoso-20260305-b1c3
cna review complete --engagement-id contoso-20260305-b1c3
cna report generate --engagement-id contoso-20260305-b1c3
cna publish run --engagement-id contoso-20260305-b1c3 --cloud azure \
  --storage-account <ACCOUNT> --container contoso-20260305-b1c3

# --- AWS only ---
cna init --client acme --platform aws
cna discover aws --engagement-id acme-20260305-a3f2 \
  --org-role arn:aws:iam::123456789012:role/CNA-ReadOnly
cna analyze --engagement-id acme-20260305-a3f2 --aws
cna report preview --engagement-id acme-20260305-a3f2
cna review complete --engagement-id acme-20260305-a3f2
cna report generate --engagement-id acme-20260305-a3f2
cna publish run --engagement-id acme-20260305-a3f2 --cloud aws \
  --bucket <BUCKET>
```

### 3. Dual-Cloud Engagement

```bash
cna init --client enterprise --platform aws --platform azure
cna discover aws  --engagement-id enterprise-20260305-c9d1 --org-role arn:...
cna discover azure --engagement-id enterprise-20260305-c9d1 --tenant-id ...
cna analyze --engagement-id enterprise-20260305-c9d1 --aws --azure
cna report generate --engagement-id enterprise-20260305-c9d1
cna publish run --engagement-id enterprise-20260305-c9d1 --cloud aws --bucket <BUCKET>
```

---

## CI/CD Workflows

| Workflow | File | Trigger | What It Does |
|---|---|---|---|
| CI | `ci.yml` | Push/PR to `main`, `develop` | Secret scan → lint → test (3.11+3.12) → module validation → Docker build smoke test |
| Release | `release.yml` | `git tag v*.*.*` | Builds multi-platform GHCR image, creates GitHub Release with changelog |
| CD Publish | `cd-publish.yml` | `workflow_dispatch` | Runs `cna publish run` in container via OIDC — no long-lived keys |
| Azure Runtime Deploy | `deploy-azure-runtime.yml` | `workflow_dispatch`, schedule | Terraform plan/apply, direct Azure evidence queries, threshold enforcement, Front Door promotion control, certificate expiry and renewal-aware verification |

### Required Repository Secrets

Set these in **GitHub → Settings → Secrets and variables → Actions → Secrets**:

| Secret | Used By | Description |
|---|---|---|
| `CNA_AWS_ROLE_ARN` | `cd-publish.yml` | ARN of `CNA-Publish` IAM role (OIDC) |
| `CNA_PUBLISH_BUCKET` | `cd-publish.yml` | S3 bucket name for delivery portal |
| `CNA_AZURE_CLIENT_ID` | `cd-publish.yml`, `deploy-azure-runtime.yml` | Azure app registration client ID (OIDC) |
| `CNA_AZURE_TENANT_ID` | `cd-publish.yml`, `deploy-azure-runtime.yml` | Azure tenant ID |
| `CNA_AZURE_SUBSCRIPTION_ID` | `cd-publish.yml`, `deploy-azure-runtime.yml` | Azure subscription ID for portal storage and runtime operations |
| `FRONTDOOR_CERTIFICATE_PFX_PASSWORD` | `deploy-azure-runtime.yml` | Password for certificate import or rotation workflow fallback |

### Required Repository Variables

Set these in **GitHub → Settings → Secrets and variables → Actions → Variables**:

| Variable | Used By | Description |
|---|---|---|
| `TFSTATE_RESOURCE_GROUP` | `deploy-azure-runtime.yml` | Terraform backend resource group |
| `TFSTATE_STORAGE_ACCOUNT` | `deploy-azure-runtime.yml` | Terraform backend storage account |
| `TFSTATE_CONTAINER` | `deploy-azure-runtime.yml` | Terraform backend blob container |
| `APPLICATION_INSIGHTS_NAME` | `deploy-azure-runtime.yml` | Application Insights instance used for canary telemetry evaluation |
| `KEY_VAULT_NAME` | `deploy-azure-runtime.yml` | Key Vault name for certificate monitoring and rotation evidence |
| `FRONTDOOR_CERTIFICATE_NAME` | `deploy-azure-runtime.yml` | Key Vault certificate name associated with Front Door |
| `FRONTDOOR_CERTIFICATE_PFX_PATH` | `deploy-azure-runtime.yml` | Certificate bundle path used by renewal/rotation fallback import logic |

> `GITHUB_TOKEN` is automatic — no setup needed. All workflows use it for GHCR push, release creation, and release-catalog commits.

### No Secrets Needed for CI

`ci.yml` requires only `GITHUB_TOKEN` (automatic). The secret-scan, lint, test, and Docker build jobs run on every push with zero configuration.

---

## Workflows: Ready to Run

| Workflow | Ready? | Needs Before First Run |
|---|---|---|
| `ci.yml` | ✅ Ready now | Nothing — runs on next push |
| `release.yml` | ✅ Ready | `git tag v0.1.0 && git push --tags` |
| `cd-publish.yml` | ⚠ Needs secrets | `CNA_AWS_ROLE_ARN` + `CNA_PUBLISH_BUCKET` (AWS) **or** Azure secrets (Azure) |
| `deploy-azure-runtime.yml` | ⚠ Needs Azure secrets and variables | OIDC credentials, Terraform backend variables, Application Insights, Key Vault, and Front Door certificate settings |

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
│   ├── findings_schema.py   # observed_state + severity + framework mappings
│   ├── persistence.py       # EngagementStore — atomic writes, audit log
│   ├── auth.py              # STS AssumeRole + DefaultAzureCredential
│   └── escalation_engine.py # DD-016: CRITICAL finding alerts
├── diagram_engine/        # .drawio + Mermaid + PNG
├── modules/               # AWS + Azure discovery
├── ai_engine/             # 11 AWS + 7 Azure rules, MCP enrichment, hedge detection
├── report_engine/         # PDF + PPTX + HTML + regional EN/JA
└── delivery_portal/       # S3 + Azure Blob, portal HTML, retention, access links
documentation/
├── deployment-guide.md    # ← START HERE for deployment
├── secrets-reference.md   # Every secret, variable, and value explained
├── cicd-iac-report.md     # CI/CD audit and hardening report
├── architecture/          # Phase docs + Azure hardening sequence
├── design/                # DD-001 through DD-019
├── policies/              # Data handling, LZ scope, JA translation
├── client-packet/         # Welcome packet, env form, permission guide
└── development/           # Module guide, diagram generation, branching
```

---

## Azure Hardening Sequence

The Azure operational hardening trail is now documented through:
- `documentation/architecture/33-frontdoor-outputs-and-live-signal-wiring.md`
- `documentation/architecture/34-direct-query-verification-and-traffic-control-intent.md`
- `documentation/architecture/35-direct-azure-queries-and-live-evidence-collection.md`
- `documentation/architecture/36-threshold-enforced-verification-and-promotion-control.md`
- `documentation/architecture/37-progressive-rollout-and-renewal-verification.md`

These documents capture the move from simulated evidence to direct Azure verification, threshold-enforced release gating, progressive rollout control, and renewal-aware certificate governance.

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

## Required IAM / RBAC

### AWS Discovery — `CNA-ReadOnly` role in every member account
See [`cna/modules/network/module.yaml`](cna/modules/network/module.yaml)

### AWS Publish — `CNA-Publish` role
`s3:PutObject`, `s3:PutBucketCors`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket`
See [`documentation/deployment-guide.md`](documentation/deployment-guide.md)

### Azure Discovery
**Reader** at root Management Group · **Management Group Reader** at tenant root

### Azure Publish
**Storage Blob Data Contributor** on storage account

### Azure Runtime Delivery Hardening
- OIDC-enabled application with subscription-scoped access for Terraform and monitoring queries
- Permissions to query Azure Monitor metrics and Application Insights
- Permissions to read and manage Front Door route and origin configuration
- Permissions to read Key Vault certificate state and perform approved rotation workflows

---

## Security

- All GitHub Actions pinned to SHA digest (supply chain hardening)
- `detect-secrets` + `gitleaks` on every commit via pre-commit
- `gitleaks-action` in CI on every push and PR
- Container runs as non-root user (uid/gid 1001) — verified in CI smoke test
- `.dockerignore` prevents `.env`, `secrets/`, `engagements/` from entering image layers
- OIDC for all CI/CD cloud credentials — no long-lived keys stored as secrets
- Pre-signed URLs and SAS tokens never stored — metadata only
- 7-day hard cap on all client access link TTLs
- 90-day engagement data retention enforced in code (DD-019)
- Azure release approval is now backed by direct telemetry, rollout, and certificate evidence checks

---

## First Deployment

```bash
# 1. Set required secrets in GitHub Settings → Secrets and variables → Actions
#    (see documentation/secrets-reference.md for every value explained)

# 2. Tag and push to trigger the release workflow
git tag v0.1.0
git push origin v0.1.0
# → GHCR image published at ghcr.io/saulpatinojr/mvp-cloud_network_assessment:0.1.0
# → GitHub Release created with changelog

# 3. Run your first engagement (single cloud recommended)
cna init --client <CLIENT> --platform azure   # or --platform aws
# Follow Quick Start above
```

See [`documentation/deployment-guide.md`](documentation/deployment-guide.md) for the complete pre-go-live checklist.

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
