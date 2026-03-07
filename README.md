# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/08-ci.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/08-ci.yml)
[![Release](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/09-release.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/09-release.yml)

A professional multi-user web platform for cloud network assessments across AWS and Azure.
Analysts run discoveries, AI-powered analysis, and generate executive-ready reports.
Clients receive deliverables through a time-limited, authenticated delivery portal.
The platform is deployed as three Azure Container Apps behind Azure Front Door, backed by
PostgreSQL and authenticated via Microsoft Entra ID.

> **Web platform architecture complete. Three-container deployment (cna-api + cna-worker + cna-web) with PostgreSQL, Entra ID auth, and full Terraform IaC. See `.github/workflows/README.md` for the first deployment checklist.**

---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation (Python CLI) | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | ⚠️ Partial — azure_discovery.py complete; azure_network/security stubs remain | 2026-03-05 |
| D | AI Analysis Engine | ✅ Complete | 2026-03-05 |
| E | Report Generation | ✅ Complete | 2026-03-05 |
| F | Delivery Portal | ✅ Complete | 2026-03-05 |
| — | CI/CD + IaC Hardening | ✅ Complete | 2026-03-06 |
| — | Azure Operational Hardening | ✅ Complete | 2026-03-06 |
| — | Azure Infra Deployment Reference | ✅ Complete | 2026-03-07 |
| — | **Web Platform Buildout** | ✅ Complete | 2026-03-07 |
| — | Phase C: Discovery Stubs | 🔧 In Progress | — |
| — | AWS Provider Expansion | ⏳ Next | — |

---

## Current Delivery State

The platform is now a fully deployable multi-user web application:

- **cna-api** — Python FastAPI container (internal, not internet-facing)
- **cna-worker** — Python background worker container (no HTTP ingress)
- **cna-web** — Next.js 15 container (public via Azure Front Door, port 3000)
- **PostgreSQL Flexible Server** — VNet-delegated, private DNS zone, Prisma ORM
- **Microsoft Entra ID** — analyst/reviewer/client/admin role model via NextAuth v5
- **Azure Front Door Standard** — WAF + CDN, TLS termination, origin = cna-web FQDN
- **Azure OpenAI** — optional AI enrichment with offline fallback (DD-003)
- **Azure Key Vault** — all platform secrets; synced to GitHub via workflow 05

The Azure delivery path additionally includes direct Azure Monitor and Application Insights
verification queries, threshold-based pass/fail gating, Front Door progressive rollout
control, and renewal-aware certificate governance.

AWS platform parity is planned as the next implementation track.

---

## Quick Start

### Local Development (CLI + Python)

```bash
# Python 3.11 or 3.12
pip install -e .[dev]

# Pre-commit hooks (runs gitleaks + ruff on every commit)
pre-commit install
pre-commit run --all-files

# Copy and fill environment file
cp .env.example .env
# Edit .env — see documentation/deployment-guide.md for every variable explained
```

### Local Development (Web Platform)

```bash
cd apps/cna-web
cp .env.example .env.local
# Fill in DATABASE_URL, NEXTAUTH_SECRET, AZURE_AD_* values
npm install
npm run db:migrate   # Runs Prisma migrations against local PostgreSQL
npm run dev          # http://localhost:3000
```

### Cloud Deployment

**See [`.github/workflows/README.md`](.github/workflows/README.md) for the complete step-by-step first deployment checklist.**

Summary of the numbered workflow sequence:

```
01 → Bootstrap Terraform backend (one-time)
02 → Build & publish all three container images to GHCR
03 → Deploy Azure infrastructure via Terraform (dev/prod)
05 → Pull secrets from Key Vault → .env artifact (validation)
06 → Fast image refresh — code-only deploys, no Terraform
07 → CD publish — deliver reports to client portals
08 → CI — lint, test, secret scan (runs on every push)
09 → Release — git tag → GHCR semver tag + GitHub Release
```

### Single-Cloud CLI Test (Recommended for API Testing)

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

---

## CI/CD Workflows

Full workflow documentation with execution order, duration, and first deployment checklist is in
[`.github/workflows/README.md`](.github/workflows/README.md).

| # | File | Trigger | What It Does |
|---|---|---|---|
| 01 | `01-bootstrap-backend.yml` | Manual (one-time) | Creates Azure RG + Storage Account for Terraform remote backend |
| 02 | `02-build-and-publish-images.yml` | Push to `main` (apps/**), manual | Builds and pushes cna-api, cna-worker, cna-web to GHCR; smoke tests |
| 03 | `03-deploy-azure-dev.yml` | Manual | Terraform plan + apply for dev/prod; post-deploy health verification; nightly drift detection |
| 05 | `05-sync-env-from-keyvault.yml` | Manual | Pulls all platform secrets from Key Vault → 1-day `.env` artifact |
| 06 | `06-refresh-containers.yml` | Manual | Fast image update via `az containerapp update` — no Terraform |
| 07 | `07-cd-publish.yml` | Push to `main` | Delivers reports and assets to client portals |
| 08 | `08-ci.yml` | Push/PR to `main` | Secret scan → ruff → mypy → pytest → eslint → Next.js build |
| 09 | `09-release.yml` | `git tag v*` | Tags GHCR images with semver + creates GitHub Release |

### Required Repository Secrets

Set these in **GitHub → Settings → Secrets and variables → Actions → Secrets**:

| Secret | Used By | Description |
|---|---|---|
| `AZURE_CLIENT_ID` | 03, 05, 06 | OIDC app registration Client ID (federated credential) |
| `AZURE_TENANT_ID` | 03, 05, 06 | Azure AD tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | 03, 05, 06 | Azure subscription ID |
| `CNA_POSTGRES_ADMIN_PASSWORD` | 03 | PostgreSQL admin password (min 8 chars, mixed case + special) |
| `CNA_ENTRA_CLIENT_SECRET` | 03 | Entra ID OAuth2 client secret for NextAuth |
| `CNA_NEXTAUTH_SECRET` | 03 | NextAuth JWT signing secret (`openssl rand -base64 32`) |
| `FRONTDOOR_CERTIFICATE_PFX_PASSWORD` | 03 | Password for custom TLS cert (optional) |
| `CNA_AWS_ROLE_ARN` | 07 | ARN of `CNA-Publish` IAM role (OIDC) |
| `CNA_PUBLISH_BUCKET` | 07 | S3 bucket name for AWS client delivery portal |

### Required Repository Variables

Set these in **GitHub → Settings → Secrets and variables → Actions → Variables**:

| Variable | Used By | Description |
|---|---|---|
| `TFSTATE_RESOURCE_GROUP` | 03 | Terraform state resource group |
| `TFSTATE_STORAGE_ACCOUNT` | 03 | Terraform state storage account |
| `TFSTATE_CONTAINER` | 03 | Terraform state blob container |
| `CNA_ENTRA_CLIENT_ID` | 03 | Entra ID application client ID |
| `CNA_NEXTAUTH_URL` | 03 | Canonical URL of deployed web app (Front Door hostname) |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | 03 | OpenAI model deployment name (e.g. `gpt-4o`) |
| `APPLICATION_INSIGHTS_NAME` | 03 | App Insights resource name (for health queries) |
| `KEY_VAULT_NAME` | 03, 05 | Key Vault name (exported from Terraform) |
| `FRONTDOOR_CERTIFICATE_NAME` | 03 | Key Vault certificate name for Front Door (optional) |
| `FRONTDOOR_CERTIFICATE_PFX_PATH` | 03 | Repo-relative path to PFX bundle (optional) |

> `GITHUB_TOKEN` is automatic — no setup needed. All workflows use it for GHCR push and release creation.

### No Secrets Needed for CI

`08-ci.yml` requires only `GITHUB_TOKEN` (automatic). Secret scan, lint, test, and Docker build jobs run on every push with zero configuration.

---

## Workflows: Ready to Run

| Workflow | Ready? | Needs Before First Run |
|---|---|---|
| `08-ci.yml` | ✅ Ready now | Nothing — runs on next push |
| `09-release.yml` | ✅ Ready | `git tag v0.1.0 && git push --tags` |
| `01-bootstrap-backend.yml` | ⚠ Needs OIDC secrets | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` |
| `02-build-and-publish-images.yml` | ✅ Ready now | Nothing — runs on next push to `main` |
| `03-deploy-azure-dev.yml` | ⚠ Needs all secrets + variables | Run 01 and 02 first; see `.github/workflows/README.md` checklist |
| `05-sync-env-from-keyvault.yml` | ⚠ After 03 completes | Run after first Terraform deploy to validate all KV secrets |
| `06-refresh-containers.yml` | ⚠ After 03 completes | Use after 02 to do fast code-only deploys |
| `07-cd-publish.yml` | ⚠ Needs AWS or Azure secrets | `CNA_AWS_ROLE_ARN` + `CNA_PUBLISH_BUCKET` (AWS) or Azure OIDC secrets |

---

## Architecture

### Container Topology

```
                    ┌─────────────────────────────────────────────┐
                    │           Azure Front Door Standard           │
                    │     WAF · CDN · TLS · Custom Domain (opt.)   │
                    └──────────────────────┬──────────────────────┘
                                           │ HTTPS
                    ┌──────────────────────▼──────────────────────┐
                    │         cna-web   (Next.js 15)               │
                    │  • Entra ID login via NextAuth v5            │
                    │  • Engagement dashboard (ANALYST/REVIEWER)   │
                    │  • Client deliverable portal (CLIENT)        │
                    │  • Role: ANALYST | REVIEWER | CLIENT | ADMIN │
                    └──────────┬─────────────────────┬────────────┘
                               │ internal VNet        │ Prisma
              ┌────────────────▼──────────┐  ┌───────▼──────────────┐
              │   cna-api  (FastAPI)       │  │  PostgreSQL Flexible  │
              │   internal only           │  │  Server (VNet-delg.)  │
              │   discovery triggers      │  │  private DNS zone     │
              │   report endpoints        │  └──────────────────────┘
              └────────────────┬──────────┘
                               │
              ┌────────────────▼──────────┐
              │  cna-worker  (Python)      │
              │  background jobs           │
              │  AI analysis via OpenAI    │
              │  report generation         │
              └───────────────────────────┘
```

### Repository Layout

```
apps/
└── cna-web/                 # Next.js 15 web platform
    ├── app/                 # App Router pages (dashboard, auth, health)
    ├── lib/                 #   auth.ts (NextAuth v5) · prisma.ts
    ├── prisma/schema.prisma # User · Engagement · Finding · Deliverable models
    └── Dockerfile           # Multi-stage; prisma migrate deploy on start
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
├── diagram_engine/          # .drawio + Mermaid + PNG
├── modules/                 # AWS + Azure discovery
├── ai_engine/               # 11 AWS + 7 Azure rules, MCP enrichment, hedge detection
├── report_engine/           # PDF + PPTX + HTML + regional EN/JA
└── delivery_portal/         # S3 + Azure Blob, portal HTML, retention, access links
infra/terraform/
├── environments/azure/dev/  # Dev environment: main.tf · variables.tf · outputs.tf
└── providers/azure/
    ├── compute/             # 3 Container Apps (api internal, web external, worker)
    ├── database/            # PostgreSQL Flexible Server + private DNS
    ├── identity/            # Managed identity + Key Vault
    ├── ai/                  # Azure OpenAI + Application Insights
    ├── network/             # VNet + subnets (apps 10.40.1, pe 10.40.2, db 10.40.3)
    ├── security/            # Front Door · WAF · private endpoints · postgres DNS zone
    ├── storage/             # Blob storage for engagement deliverables
    └── runtime/             # RBAC + Key Vault secrets (database-url, nextauth, entra)
.github/workflows/           # 01–09 numbered workflow sequence
documentation/
├── deployment-guide.md      # ← START HERE for full deployment
├── secrets-reference.md     # Every secret, variable, and value explained
├── cicd-iac-report.md       # CI/CD audit and hardening report
├── architecture/            # Phase docs + Azure hardening sequence (33–39)
├── design/                  # DD-001 through DD-019
├── policies/                # Data handling, LZ scope, JA translation
├── client-packet/           # Welcome packet, env form, permission guide
└── development/             # Module guide, diagram generation, branching
```

---

## Azure Hardening Sequence

The Azure operational hardening trail is documented through:
- `documentation/architecture/33-frontdoor-outputs-and-live-signal-wiring.md`
- `documentation/architecture/34-direct-query-verification-and-traffic-control-intent.md`
- `documentation/architecture/35-direct-azure-queries-and-live-evidence-collection.md`
- `documentation/architecture/36-threshold-enforced-verification-and-promotion-control.md`
- `documentation/architecture/37-progressive-rollout-and-renewal-verification.md`

These documents capture the move from simulated evidence to direct Azure verification, threshold-enforced release gating, progressive rollout control, and renewal-aware certificate governance.

## Azure Infra Deployment Reference

**For first deployment: start with [`.github/workflows/README.md`](.github/workflows/README.md).**
It contains the complete numbered checklist (Entra app registration → secrets → bootstrap → build → deploy → validate).

`documentation/architecture/38-azure-infra-deployment-reference.md` is the architecture
reference covering:
- Complete resource inventory and Terraform module mapping
- Workflow sequence (bootstrap → image build → Terraform deploy → Key Vault post-config)
- OIDC setup steps (exact CLI commands, no long-lived keys)
- Secrets and Variables checklist before first deploy
- Stale state and cycle prevention mitigations (learned from MVP-Azure_Spec_Builder)

`documentation/architecture/39-platform-architecture-revised.md` documents the web platform
scope correction — why the platform moved from a single-user CLI tool to a multi-user web
application, the three-container architecture decision, PostgreSQL + Entra ID rationale, and
the Terraform module additions made in this revision.

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

**See [`.github/workflows/README.md`](.github/workflows/README.md) for the complete step-by-step checklist.**

High-level sequence:

```bash
# 1. Create Entra ID App Registration
#    Redirect URI: https://<your-frontdoor-domain>/api/auth/callback/microsoft-entra-id
#    Grant: openid, profile, email, User.Read

# 2. Set all GitHub Secrets and Variables (see workflow 03 table above)

# 3. Run workflow 01 to bootstrap Terraform backend (one-time)

# 4. Push to main — workflow 02 auto-builds all three container images

# 5. Run workflow 03 (environment: dev) — first Terraform deploy (~20 min)
#    → After apply, copy the Front Door hostname from outputs
#    → Update CNA_NEXTAUTH_URL GitHub Variable to the Front Door hostname
#    → Re-run workflow 03 to apply the updated NextAuth URL

# 6. Run workflow 05 to validate all Key Vault secrets are populated

# 7. Navigate to https://<frontdoor-hostname> — sign in with Entra ID
```

See [`documentation/deployment-guide.md`](documentation/deployment-guide.md) for the full pre-go-live checklist including AWS setup, discovery RBAC, and client portal configuration.

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
