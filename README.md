# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/020-test-codebase.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/020-test-codebase.yml)
[![Release](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/021-release-version.yml/badge.svg)](https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/actions/workflows/021-release-version.yml)

A professional multi-user web platform for cloud network assessments across AWS and Azure.
Analysts run discoveries, AI-powered analysis, and generate executive-ready reports.
Clients receive deliverables through a time-limited, authenticated delivery portal.
The platform is deployed as three Azure Container Apps behind Azure Front Door, backed by
PostgreSQL and authenticated via Microsoft Entra ID.

> **Version 1.0.0 Released as of 2026-05-28. Platform is Production-Ready (General Availability).**
> All hardening phases, security audits, and multi-cloud expansions are completed. See the [CHANGELOG.md](CHANGELOG.md) for full version history.


---

## Phase Status

| Phase | Name | Status | Signed Off |
|---|---|---|---|
| A | Platform Foundation (Python CLI) | ✅ Complete | 2026-03-05 |
| B | Diagram Engine | ✅ Complete | 2026-03-05 |
| C | Discovery Engine | ✅ Complete | 2026-03-05 |
| D | AI Analysis Engine | ✅ Complete | 2026-03-05 |
| E | Report Generation | ✅ Complete | 2026-03-05 |
| F | Delivery Portal | ✅ Complete | 2026-03-05 |
| — | CI/CD + IaC Hardening | ✅ Complete | 2026-03-06 |
| — | Azure Operational Hardening | ✅ Complete | 2026-03-06 |
| — | Azure Infra Deployment Reference | ✅ Complete | 2026-03-07 |
| — | Web Platform Buildout | ✅ Complete | 2026-03-07 |
| — | **Web Platform Alpha** | ✅ Complete | 2026-04-14 |
| — | Phase C: Discovery Stubs (AWS) | ✅ Complete | 2026-04-20 |
| — | AWS Provider Expansion | ✅ Complete | 2026-05-28 |

---

## Alpha Features Shipped

All features below were built, deployed, and validated in the Alpha stage (ending 2026-04-14).

### Discovery

- **Per-subscription sync groups** — Each Azure credential/subscription runs as its own independent `DiscoveryJob`. Progress bars, logs, run count, and completion timestamps are tracked individually. "Re-sync all" fires one job per credential rather than a merged batch job.
- **Multi-subscription topology merge** — Inventory, presentation dashboard, and all deliverable generators merge topology from all credential sync groups (deduplicating by `subscription_id`). No data from any subscription is dropped.

### Findings & Analysis

- **Findings count display** — Header shows the count of unique issue groups (deduplicated by severity + category + title). The subtitle shows raw finding count, live-scanned vs. AI-generated breakdown, and filter state.
- **AI-powered findings** — Azure OpenAI analysis generates per-resource findings enriched with Microsoft Learn documentation fetched at generation time.

### Deliverables

- **Five assessment types** — `COMPREHENSIVE_ASSESSMENT` (HTML), `EXECUTIVE_SUMMARY`, `TECHNICAL_FINDINGS`, `REMEDIATION_PLAN`, `SPECIALIZATION_REPORT` (all Markdown). Generate individually or all at once.
- **Comprehensive Assessment output** — Fixed HTML vs. Markdown conflict; COMPREHENSIVE_ASSESSMENT always produces a complete self-contained HTML document.
- **Generate All** — Fires all five types in parallel, stores successful ones; reports partial success count.
- **MS Learn enrichment** — Live Microsoft Learn API fetch at generation time, injected into the AI prompt per finding category.
- **Multi-credential context** — All generators receive the full merged topology, all credentials' subscription info, and the list of previously generated assessments as context.

### Interactive Assessment

- **AI generation on every create** — "Create Interactive Assessment" calls Azure OpenAI (COMPREHENSIVE_ASSESSMENT type) with merged topology + all findings + all documents + MS Learn context. Fresh HTML content is stored on every create/recreate.
- **View Report + Dashboard split** — The deliverables portal shows a "View Report" button (AI-generated HTML) alongside "Dashboard" (live presentation site) once content exists.
- **Generation feedback** — Button shows "Generating with AI…" with a 60-second hint; errors surface in the UI.

### Presentation Dashboard

- **Correct subscription counts** — All five presentation pages (overview, executive, technical, compliance, remediation) use the multi-credential topology merge — never a single `findFirst`. "1 subscription" on the executive summary is fixed.
- **Live metrics** — Risk score, maturity radar, severity distribution, infrastructure topology stats, remediation phases, and framework mapping (NIST CSF, CIS v8, Azure CAF) all derive from live DB data.

---

## Current Delivery State

The platform is a fully deployable multi-user web application:

- **cna-api** — Python FastAPI container (internal, not internet-facing)
- **cna-worker** — Python background worker container (no HTTP ingress)
- **cna-web** — Next.js 15 container (public via Azure Front Door, port 3000)
- **PostgreSQL Flexible Server** — VNet-delegated, private DNS zone, Prisma ORM (7 migrations)
- **Microsoft Entra ID** — analyst/reviewer/client/admin role model via NextAuth v5
- **Azure Front Door Standard** — WAF + CDN, TLS termination, origin = cna-web FQDN
- **Azure OpenAI** — AI enrichment with MS Learn context injection; error messages surface in UI
- **Azure Blob Storage** — engagement deliverables and uploaded documents
- **Azure Key Vault** — all platform secrets; synced to GitHub via workflow 011

---

## Quick Start

### Local Development (Web Platform)

```bash
cd apps/cna-web
cp .env.example .env.local
# Fill in DATABASE_URL, NEXTAUTH_SECRET, AZURE_AD_* values
npm install
npm run db:migrate   # Prisma migrate deploy against local PostgreSQL
npm run dev          # http://localhost:3000
```

### Local Development (CLI + Python)

```bash
# Python 3.11 or 3.12
pip install -e .[dev]

# Pre-commit hooks (runs gitleaks + ruff on every commit)
pre-commit install
pre-commit run --all-files

cp .env.example .env
# Edit .env — see documentation/deployment-guide.md for every variable
```

### Cloud Deployment

**See [`.github/workflows/README.md`](.github/workflows/README.md) for the complete
step-by-step first-deployment checklist.**

Numbered workflow sequence:

```
000 → Bootstrap Terraform backend (one-time)
010 → Validate all GitHub Secrets, Variables, and Azure OIDC access
011 → Pull secrets from Key Vault → .env artifact (validation)
012 → Fast image refresh — code-only deploys, no Terraform
020 → CI — lint, test, secret scan (runs on every push)
021 → Release — git tag → GHCR semver tag + GitHub Release
022 → Publish — deliver reports to client portals
030 → Build & publish all three container images to GHCR
031 → Deploy Azure infrastructure + containers via Terraform
```

---

## CI/CD Workflows

Full workflow documentation is in [`.github/workflows/README.md`](.github/workflows/README.md).

| File | Trigger | What It Does |
|---|---|---|
| `000-bootstrap-backend.yml` | Manual (one-time) | Creates Azure RG + Storage Account for Terraform remote backend |
| `010-validate-prereqs.yml` | Manual | Validates all GitHub secrets, variables, and Azure OIDC access |
| `011-sync-keys.yml` | Manual | Pulls all platform secrets from Key Vault → 1-day `.env` artifact |
| `012-fast-redeploy.yml` | Manual | Fast image update via `az containerapp update` — no Terraform |
| `020-test-codebase.yml` | Push/PR to `main` | Secret scan → lint → test → Docker build → coverage gate |
| `021-release-version.yml` | `git tag v*.*.*` | Tags GHCR images with semver + creates GitHub Release |
| `022-publish-portal.yml` | Manual | Delivers reports and assets to client portals (Azure or AWS) |
| `030-build-images.yml` | Push to `main` (apps/**) or manual | Builds + pushes cna-api, cna-worker, cna-web to GHCR; writes build manifest |
| `031-deploy-azure.yml` | Manual + nightly schedule | Terraform plan → policy gates → apply → health verification; rollback support |

### Required Repository Secrets

| Secret | Used By | Description |
|---|---|---|
| `AZURE_CLIENT_ID` | 031, 011, 012 | OIDC app registration Client ID (federated credential) |
| `AZURE_TENANT_ID` | 031, 011, 012 | Azure AD tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | 031, 011, 012 | Azure subscription ID |
| `CNA_POSTGRES_ADMIN_PASSWORD` | 031 | PostgreSQL admin password (min 8 chars, mixed case + special) |
| `CNA_ENTRA_CLIENT_SECRET` | 031 | Entra ID OAuth2 client secret for NextAuth |
| `CNA_NEXTAUTH_SECRET` | 031 | NextAuth JWT signing secret (`openssl rand -base64 32`) |
| `FRONTDOOR_CERTIFICATE_PFX_PASSWORD` | 031 | Password for custom TLS cert (optional) |
| `CNA_AWS_ROLE_ARN` | 022 | ARN of `CNA-Publish` IAM role (OIDC) |
| `CNA_PUBLISH_BUCKET` | 022 | S3 bucket name for AWS client delivery portal |

### Required Repository Variables

| Variable | Used By | Description |
|---|---|---|
| `TFSTATE_RESOURCE_GROUP` | 031 | Terraform state resource group |
| `TFSTATE_STORAGE_ACCOUNT` | 031 | Terraform state storage account |
| `TFSTATE_CONTAINER` | 031 | Terraform state blob container |
| `CNA_ENTRA_CLIENT_ID` | 031 | Entra ID application client ID |
| `CNA_NEXTAUTH_URL` | 031 | Canonical URL of deployed web app (Front Door hostname) |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | 031 | OpenAI model deployment name (e.g. `gpt-4o`) |
| `APPLICATION_INSIGHTS_NAME` | 031 | App Insights resource name (for health queries, set to `none` until created) |
| `KEY_VAULT_NAME` | 031, 011 | Key Vault name (set to `none` until created) |
| `FRONTDOOR_CERTIFICATE_NAME` | 031 | Key Vault certificate name for Front Door (optional) |

> `GITHUB_TOKEN` is automatic — no setup needed. All workflows use it for GHCR push and release creation.

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
                    │  • Interactive assessment presentation site  │
                    │  • Role: ANALYST | REVIEWER | CLIENT | ADMIN │
                    └──────────┬─────────────────────┬────────────┘
                               │ internal VNet        │ Prisma (7 migrations)
              ┌────────────────▼──────────┐  ┌───────▼──────────────┐
              │   cna-api  (FastAPI)       │  │  PostgreSQL Flexible  │
              │   internal only           │  │  Server (VNet-delg.)  │
              │   /discovery/start        │  │  private DNS zone     │
              │   /health                 │  └──────────────────────┘
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
└── cna-web/                        # Next.js 15 web platform
    ├── app/(dashboard)/
    │   └── engagements/[id]/
    │       ├── connections/         # Cloud credentials + per-subscription discovery
    │       ├── discovery/           # Discovery job triggers (one job per credential)
    │       ├── inventory/           # Multi-subscription merged network inventory
    │       ├── findings/            # Grouped findings with unique-issue count
    │       ├── deliverables/        # Generate/manage AI assessments (5 types)
    │       ├── client-deliverables/ # Deliverable portal + interactive assessment
    │       └── presentation/        # Live interactive assessment dashboard (5 pages)
    ├── lib/
    │   ├── auth.ts                  # NextAuth v5 + Entra ID
    │   ├── openai.ts                # generateDeliverableContent + MS Learn enrichment
    │   ├── blob.ts                  # Azure Blob Storage for deliverables
    │   └── prisma.ts                # Prisma client singleton
    ├── prisma/
    │   ├── schema.prisma            # 15 models: User · Engagement · Finding · Deliverable
    │   └── migrations/              # 7 migrations (init → interactive-assessment)
    └── Dockerfile                   # 4-stage; migrator stage runs prisma migrate deploy
cna/
├── cli/                             # cna discover / analyze / report / publish
├── core/                            # topology_schema · findings_schema · persistence
├── modules/                         # AWS + Azure discovery modules
├── ai_engine/                       # 11 AWS + 7 Azure rules, MCP enrichment
├── report_engine/                   # PDF + PPTX + HTML + regional EN/JA
└── delivery_portal/                 # S3 + Azure Blob, portal HTML, retention
infra/terraform/
├── environments/azure/dev/          # Dev: main.tf · variables.tf · outputs.tf
├── environments/azure/prod/         # Prod: same structure
└── providers/azure/
    ├── compute/                     # 3 Container Apps (api internal, web external, worker)
    ├── database/                    # PostgreSQL Flexible Server + private DNS
    ├── identity/                    # Managed Identity + Key Vault
    ├── ai/                          # Azure OpenAI + Application Insights
    ├── network/                     # VNet + subnets (apps/pe/db)
    ├── security/                    # Front Door · WAF · private endpoints
    ├── storage/                     # Blob storage for engagement deliverables
    └── runtime/                     # RBAC + Key Vault secrets
.github/workflows/                   # 000–031 numbered workflow sequence
documentation/
├── deployment-guide.md              # ← START HERE for first deployment
├── secrets-reference.md             # Every secret, variable, and value explained
├── cicd-iac-report.md               # CI/CD audit and hardening report
├── architecture/                    # Phase docs + Azure hardening sequence (40+ docs)
├── design/                          # DD-001 through DD-019
├── policies/                        # Data handling, LZ scope, JA translation
├── client-packet/                   # Welcome packet, env form, permission guide
└── development/                     # Module guide, diagram generation, branching
```

---

## Beta: First Deployment (Clean Environment)

The dev environment is being torn down and redeployed clean as part of the Alpha→Beta transition.
Follow this sequence exactly.

### Prerequisites (one-time)

```bash
# 1. Entra ID App Registration (Azure Portal)
#    → Redirect URI: https://<frontdoor-hostname>/api/auth/callback/microsoft-entra-id
#    → Grant: openid, profile, email, User.Read
#    → Create OIDC federated credential:
#       Issuer: https://token.actions.githubusercontent.com
#       Subject: repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main

# 2. Set GitHub Secrets and Variables (see tables above)

# 3. Run workflow 000 — bootstrap Terraform backend (one-time)
```

### Deployment Sequence

```bash
# 4. Push to main — workflow 030 auto-builds all three container images

# 5. Run workflow 010 — validate all secrets/variables/OIDC before deploying

# 6. Run workflow 031 (environment: dev) — first Terraform deploy (~20 min)
#    → After apply, copy the Front Door hostname from outputs
#    → Update CNA_NEXTAUTH_URL GitHub Variable to the Front Door hostname
#    → Update Entra redirect URI to match
#    → Re-run workflow 031 to apply the updated NextAuth URL

# 7. Run workflow 011 — validate all Key Vault secrets are populated

# 8. Navigate to https://<frontdoor-hostname> — sign in with Entra ID
```

---

## Azure Hardening Sequence

Documented through architecture docs 33–37:

- `33-frontdoor-outputs-and-live-signal-wiring.md`
- `34-direct-query-verification-and-traffic-control-intent.md`
- `35-direct-azure-queries-and-live-evidence-collection.md`
- `36-threshold-enforced-verification-and-promotion-control.md`
- `37-progressive-rollout-and-renewal-verification.md`

These capture the move from simulated evidence to direct Azure verification, threshold-enforced
release gating, progressive rollout control, and renewal-aware certificate governance.

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
- Azure release gated by direct Azure Monitor + App Insights telemetry evidence

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
*Version 1.0.0 Released 2026-05-28 · Production Ready*

