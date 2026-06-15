# Cloud Network Assessment (CNA) Platform

[![CI](https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/actions/workflows/020-test-codebase.yml/badge.svg)](https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/actions/workflows/020-test-codebase.yml)
[![Release](https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/actions/workflows/021-release-version.yml/badge.svg)](https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/actions/workflows/021-release-version.yml)

A CNA-branded, multi-user web platform for cloud network assessments across AWS and Azure.
Analysts run network discoveries, AI-powered analysis, and generate presentation-ready deliverables
including an encyclopedia-grade network report. Clients receive deliverables through a
time-limited authenticated portal. Deployed as three Azure Container Apps behind Azure Front Door,
backed by PostgreSQL and authenticated via Microsoft Entra ID.

> **Current status — June 2026:** Infrastructure is being prepared for clean redeploy with `cna-*` naming only, one workload resource group per environment, and GitHub Secrets/Variables as the deployment source of truth.

---

## Platform Status

| Area | Status | Notes |
|---|---|---|
| Platform foundation + CLI | ✅ GA | Python `cna` package |
| Azure discovery engine | ✅ GA | VNet, peerings, gateways, firewall, NSG, UDR, flow logs |
| AWS discovery stubs | ✅ GA | VPC, TGW, security groups |
| AI analysis engine | ✅ GA | Azure Foundry (Claude), 11 AWS + 7 Azure rules |
| Web platform (Next.js) | ✅ GA | Entra ID auth, engagement workflow |
| CNA visual system | ✅ Merged | Navy/teal palette, Aeonik font, SVG brand assets |
| East-West / North-South taxonomy | ✅ Merged | `traffic_direction` on all findings |
| FinOps signals (AZ-COST-001–005) | ✅ Merged | Orphaned PIPs, idle gateways, oversized SKUs, NAT/FW waste |
| BC/DR signals (AZ-BCDR-001–005) | ✅ Merged | Zone redundancy, active-active, single-gateway gaps |
| Topology classifier | ✅ Merged | mesh / hub_spoke / vwan / isolated |
| Future-state Draw.io | ✅ Merged | Recommended topology diff, dashed bright-teal new resources |
| Stat Masters pivot layer | ✅ Merged | PowerBI-style aggregation, TanStack pivot grid |
| Encyclopedia report | ✅ Merged | 6-chapter, Condensed + Expanded editions, WeasyPrint PDF |
| Grounded copilot chat | ✅ Merged | Azure Foundry, stat-master context, citation chips |
| Frontend UX journey (8 steps) | ✅ Merged | Traffic, FinOps, Resilience, Discovery, Book Mode pages |
| CAF naming convention | ✅ Merged | `cna-[env]-[region_short]`, single workload RG per env |
| Teardown workflow (032) | ✅ Merged | `DESTROY`-gated, optional state wipe |
| CI — lint/test | ✅ Passing | ruff, pytest 3.13 + 3.14, Docker build smoke |
| Azure deployment | ⏳ Pending | Awaiting teardown + clean redeploy with new naming |

---

## Architecture

### Container topology

```
                    ┌──────────────────────────────────────────┐
                    │          Azure Front Door Premium         │
                    │    WAF · CDN · TLS · Custom Domain (opt.) │
                    └─────────────────────┬────────────────────┘
                                          │ HTTPS
                    ┌─────────────────────▼────────────────────┐
                    │        cna-[env]-[region]-ca-web          │
                    │        Next.js 19 / React 19              │
                    │  • Entra ID login (NextAuth v5)           │
                    │  • 8-step engagement journey              │
                    │  • Book Mode encyclopedia report          │
                    │  • Copilot chat panel (grounded)          │
                    └───────────┬──────────────────┬───────────┘
                                │ internal         │ Prisma ORM
              ┌─────────────────▼────────┐  ┌──────▼─────────────────┐
              │  cna-[env]-[region]-ca-api │  │  cna-[env]-[region]-psql │
              │  FastAPI — internal only  │  │  PostgreSQL Flexible    │
              │  /metrics  /chat  /reports│  │  VNet-delegated         │
              └─────────────────┬─────────┘  └────────────────────────┘
                                │
              ┌─────────────────▼────────┐
              │  cna-[env]-[region]-ca-worker       │
              │  Python background worker │
              │  Discovery · AI analysis  │
              │  Report generation (PDF)  │
              └──────────────────────────┘
```

### Resource group layout (single RG per environment)

All resources — including AI Foundry (deployed to `eastus2`) — share one resource group:

```
rg-cna-dev-scus
├── cna-dev-scus-vnet               Virtual network
├── cna-dev-scus-cae                Container Apps Environment
├── cna-dev-scus-ca-api             Container App (API)
├── cna-dev-scus-ca-worker          Container App (worker)
├── cna-dev-scus-ca-web             Container App (web)
├── cna-dev-scus-psql               PostgreSQL Flexible Server
├── cna-dev-scus-kv                 Key Vault
├── cna-dev-scus-id                 Managed Identity
├── cnadevscusst                    Storage Account
├── cna-dev-scus-afd                Front Door profile
├── cnadevscusfdfp                  Front Door WAF policy
├── cna-dev-scus-nsg                Network Security Group
├── cna-dev-scus-log                Log Analytics workspace
├── cna-dev-scus-appi               Application Insights
├── cna-dev-eus2-aif                AI Foundry account
└── cna-dev-eus2-aif-proj           AI Foundry project
```

### Repository layout

```
apps/
├── cna-web/          Next.js 19 web platform (8-step journey, encyclopedia, copilot)
├── cna-api/          FastAPI — metrics, chat, reports, discovery routers
└── cna-worker/       Python background worker — discovery + report generation
cna/
├── core/             topology_schema · findings_schema · stat_masters · engagement
├── modules/          AWS + Azure discovery, FinOps signals, BC/DR signals, topology classifier
├── ai_engine/        Analysis engine, recommendation engine, chat agent (Foundry)
├── report_engine/    Encyclopedia renderer, WeasyPrint PDF, radar chart SVG
└── diagram_engine/   Draw.io generator, future-state model
infra/terraform/
├── environments/azure/dev/   Dev environment root module
├── environments/azure/prod/  Prod environment root module
└── providers/azure/          Reusable modules: ai, compute, database, identity,
                              security, storage, runtime
.github/workflows/            000–032 numbered workflow sequence
GitHub Wiki                   Documentation and ADRs migrated to https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/wiki
TODO.md                       Canonical open redeploy, validation, footprint, and enhancement tasks
scripts/                      Remove-DriftedResources.ps1, operational runbooks
```

---

## Quick start

### Local development (web)

```bash
cd apps/cna-web
cp .env.example .env.local
# Fill in DATABASE_URL, NEXTAUTH_SECRET, AZURE_AD_* values
npm install
npm run db:migrate
npm run dev          # http://localhost:3000
```

### Local development (Python CLI)

```bash
pip install -e .[dev]
pre-commit install
cp .env.example .env
```

### Clean deployment (first time or after teardown)

```
1. Run workflow 000 — create the workload RG, bootstrap the Terraform backend, and import the RG into state (one-time per environment)
2. Run workflow 010 — validate all secrets, variables, Azure OIDC
3. Push to main   — workflow 030 auto-builds all three container images
4. Run workflow 031 (environment: dev) — Terraform apply (~20 min)
   → Copy Front Door hostname from outputs
   → Update CNA_NEXTAUTH_URL GitHub Variable + Entra redirect URI
   → Re-run 031 to apply updated NextAuth URL
5. Navigate to https://<frontdoor-hostname> — sign in with Entra ID
```

To wipe an environment and redeploy clean:

```
1. Run workflow 032 — type DESTROY to confirm teardown
2. Review its cleanup preview and confirm only CNA-owned targets are listed
3. Keep `destroy_tfstate_backend=false` unless intentionally resetting Terraform state
4. Follow deployment steps above
```

---

## CI/CD workflows

| File | Trigger | Purpose |
|---|---|---|
| `000-bootstrap-backend.yml` | Manual (one-time per environment) | Creates workload RG, provisions tfstate backend in a separate convention-based RG, imports app RG into state |
| `010-validate-prereqs.yml` | Manual | Validates all secrets, variables, OIDC |
| `011-sync-keys.yml` | Manual | Pulls Key Vault secrets → `.env` artifact |
| `012-fast-redeploy.yml` | Manual | Fast image update via `az containerapp update` |
| `020-test-codebase.yml` | Push/PR to `main` | Secret scan → ruff lint → pytest → Docker smoke |
| `021-release-version.yml` | `git tag v*.*.*` | Tags GHCR images + creates GitHub Release |
| `022-publish-portal.yml` | Manual | Delivers reports to client portals |
| `030-build-images.yml` | Push to `main` | Builds + pushes cna-api/worker/web to GHCR |
| `031-deploy-azure.yml` | Manual + nightly | Terraform plan → apply → health verification |
| `032-teardown.yml` | Manual (`DESTROY`) | Full environment teardown with safety gate |

---

## Design contracts (enforced in code)

| DD | Contract | Enforced in |
|---|---|---|
| DD-002 | `observed_state` = discovered fact only | `ObservedStateEnforcer` |
| DD-003 | Findings and recommendations are separate paths | `AnalysisEngine` vs `RecommendationEngine` |
| DD-008 | AI engine reads from store only | `AnalysisEngine` |
| DD-009 | `review_complete=True` required before PDF render | `RenderPipeline._enforce_review_gate()` |
| DD-013 | Deliverable staleness via SHA-256 checksum | `DeliverableManifest` |
| DD-019 | 90-day retention enforced | `RetentionEngine.check()` |

---

## Security

- All GitHub Actions pinned to SHA digest
- `gitleaks` + `detect-secrets` on every commit and CI push
- Containers run as non-root (uid 1001)
- OIDC for all CI/CD cloud credentials — no long-lived keys
- Azure release gated by direct Azure Monitor + App Insights evidence
- Encyclopedia/branded reports flagged `[REVIEW REQUIRED]` before client delivery
- Cost estimates in FinOps findings flagged `[VERIFY]` for analyst review

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
*CNA Platform · June 2026*
