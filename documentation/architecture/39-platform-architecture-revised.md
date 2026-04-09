# 39 — Web Platform Architecture: Scope Correction and Revised Design

**Date:** 2026-03-07
**Status:** ✅ Complete
**Preceded by:** `38-azure-infra-deployment-reference.md`

---

## Why This Document Exists

Documents 01–38 describe the CNA platform as a single-user CLI tool deployed as one Python
container. That model was correct for the MVP phase but became a structural blocker once the
engagement workflow was mapped against real delivery requirements.

This document records:

1. What the problem was
2. What the corrected architecture is
3. Which Terraform modules were added or changed
4. Which application code was added
5. Which GitHub Actions workflows were added or renamed
6. The data model introduced

---

## The Problem: Single-User CLI Does Not Scale to Delivery

The original architecture (documents 01–38) assumed one practitioner running CLI commands
locally. Discovery artifacts lived on a local filesystem. Reports were manually uploaded
to Azure Blob. There was no concept of:

- multiple analysts working on the same engagement
- a reviewer approving findings before a report is finalized
- a client logging in to view and download their deliverables
- access control distinguishing who can see what
- a persistent database tracking engagement state across CLI runs

This was appropriate for a technical proof-of-concept but not for a platform sold to enterprise
clients. The correction required adding a web tier, a relational database, and an identity layer
without discarding any of the Python CLI engine work done in phases A–F.

**Key insight from reviewing MVP-Azure_Spec_Builder:** that project demonstrated exactly the
pattern needed — Next.js 15 + PostgreSQL + Entra ID + Azure Container Apps + Prisma, all wired
together with Terraform and deployed via OIDC GitHub Actions. The CNA platform adopted the same
pattern, reusing the infrastructure decisions directly.

---

## Revised Architecture: Three Containers

### Container Map

| Container | Image | Ingress | Role |
|---|---|---|---|
| `cna-web` | `ghcr.io/saulpatinojr/cna-web` | External (port 3000) via Azure Front Door | Next.js 15 UI — engagement dashboard, report viewer, client portal |
| `cna-api` | `ghcr.io/saulpatinojr/cna-api` | Internal only (VNet) | Python FastAPI — discovery triggers, findings endpoints, status |
| `cna-worker` | `ghcr.io/saulpatinojr/cna-worker` | None (no HTTP) | Python background — AI analysis, report generation, delivery |

**Why `cna-api` is internal-only:** The web tier (`cna-web`) handles all user-facing requests.
`cna-api` is an internal service called by `cna-web` over the Azure Container Apps environment
VNet. Exposing `cna-api` externally would add an unauthenticated attack surface with no benefit.

**Why three containers instead of two:** The CLI engine (Python) cannot be combined with the
web frontend (Node.js/Next.js) without creating a polyglot container that is difficult to build,
test, and upgrade independently. Worker is separated from API to prevent long-running analysis
jobs from blocking API request handling.

### Network Topology

```
Internet → Azure Front Door (WAF, CDN, TLS)
              ↓ HTTPS
         cna-web  (Container App, external ingress)
              ↓ internal VNet call
         cna-api  (Container App, internal ingress only)
              ↓ job dispatch
         cna-worker  (Container App, no ingress)

PostgreSQL Flexible Server
  • Subnet: 10.40.3.0/24, delegated to Microsoft.DBforPostgreSQL/flexibleServers
  • Private DNS zone: privatelink.postgres.database.azure.com
  • Not reachable from internet — only from Container Apps environment VNet

Azure OpenAI
  • Private endpoint in pe-subnet (10.40.2.0/24)
  • Key Vault secret: cna-azure-openai-endpoint
  • DefaultAzureCredential preferred over API key
```

### Subnet Allocation (10.40.0.0/16)

| Subnet | CIDR | Purpose |
|---|---|---|
| `snet-cna-apps` | 10.40.1.0/24 | Container Apps environment |
| `snet-cna-pe` | 10.40.2.0/24 | Private endpoints (OpenAI, Storage) |
| `snet-cna-db` | 10.40.3.0/24 | PostgreSQL delegation |

---

## User Roles and Access Model

| Role | Can Do |
|---|---|
| `ADMIN` | Full platform access, user management |
| `ANALYST` | Create engagements, run discovery, trigger analysis, generate reports |
| `REVIEWER` | Review and approve findings; `review_complete=True` gate |
| `CLIENT` | Read-only access to their own engagement deliverables |

Roles are stored in PostgreSQL on the `User` table and enforced in Next.js middleware and
API route handlers. Role is injected into the NextAuth session via the `session` callback
in `lib/auth.ts`.

---

## Terraform Changes

### Modules Added

**`infra/terraform/providers/azure/database/`** (new)

Provisions the PostgreSQL Flexible Server:
- Server name: `psql-{name_prefix}`
- PostgreSQL version 16
- SKU: `GP_Standard_D2s_v3` (General Purpose, 2 vCores) — configurable
- VNet delegation: `Microsoft.DBforPostgreSQL/flexibleServers` on the database subnet
- Private DNS zone integration: `privatelink.postgres.database.azure.com`
- Backup retention: 7 days, geo-redundant enabled
- High availability: ZoneRedundant (configurable)
- Database: `cna` created inside the server
- No public access — only reachable within the VNet

The private DNS zone is created in the **security module** (not the database module) because
Front Door and other private endpoint DNS zones also live there, avoiding a circular dependency.
The database module receives `postgres_private_dns_zone_id` as an input variable.

### Modules Modified

**`infra/terraform/providers/azure/compute/`**

- Added `cna-web` Container App resource (`azurerm_container_app.web`)
  - `external_enabled = true` — receives traffic from Front Door
  - `target_port = 3000` — Next.js default
  - Liveness/readiness probes at `/api/health`
  - Secrets: `database-url`, `nextauth-secret`, `entra-client-secret` mounted as secret env vars
- Changed `cna-api` Container App ingress: `external_enabled = false` (was conditional)
- Added outputs: `web_id`, `web_name`, `web_fqdn`
- Added variables: `web_image`, `web_target_port`, `web_env_vars`, `web_secret_env_vars`

**`infra/terraform/providers/azure/security/`**

- Added Postgres private DNS zone: `azurerm_private_dns_zone.postgres`
  (`privatelink.postgres.database.azure.com`)
- Added VNet link for Postgres DNS zone
- Output: `postgres_private_dns_zone_id` (consumed by database module)
- Changed Azure Front Door origin from `api` FQDN to `web` FQDN
  - The public-facing entry point is the web container, not the API container
  - Health probe path changed to `/api/health` (Next.js health endpoint)
- Added `web_container_app_fqdn` and `web_container_app_id` variables
- Fixed missing `openai_endpoint_secret_name` output (was referenced in dev/outputs.tf)

**`infra/terraform/providers/azure/runtime/`**

- Removed: all `azurerm_container_app_environment_variable` resources
  - This resource type does not exist in the AzureRM Terraform provider
  - Environment variables are set within `azurerm_container_app` resource blocks
  - The compute module already had the correct `api_env_vars`/`worker_env_vars` map pattern
- Removed: duplicate `key_vault_secrets_user` RBAC assignment
  - The security module already assigns `Key Vault Secrets Officer` (a superset of Secrets User)
  - Duplicate assignment on the same principal + scope causes Terraform state drift
- Added: three Key Vault secrets with `lifecycle { ignore_changes = [value] }`:
  - `cna-database-url` — full PostgreSQL connection string for Prisma
  - `cna-nextauth-secret` — cryptographically random string for JWT signing
  - `cna-entra-client-secret` — Entra ID OAuth2 client secret for NextAuth
  - These are the secrets pulled by workflow `05-sync-env-from-keyvault.yml`

**`infra/terraform/environments/azure/dev/`**

- Added `azurerm_subnet.database` with PostgreSQL delegation at `10.40.3.0/24`
- Updated `module.compute`: passes `web_image`, `web_env_vars`, `web_secret_env_vars`,
  `container_app_secrets` (with all three platform secrets), `container_apps_internal_only = false`
- Updated `module.runtime`: replaced old vars with `database_url`, `nextauth_secret`, `entra_client_secret`
- Updated `module.security`: added `web_container_app_fqdn`, `web_container_app_id`
- Added `module.database`: wires database subnet + postgres DNS zone ID + credentials
- Added outputs: `web_fqdn`, `frontdoor_endpoint_host_name`, `database_server_name`, `database_server_fqdn`
- Added variables: `web_image`, `postgres_admin_username`, `postgres_admin_password`,
  `entra_client_id`, `entra_client_secret`, `nextauth_secret`, `nextauth_url`

---

## Application Code Added: `apps/cna-web/`

A new Next.js 15 application was scaffolded in `apps/cna-web/`. Key files:

| File | Purpose |
|---|---|
| `package.json` | Next.js 15.0.4, NextAuth v5 beta, Prisma 5.22, @azure/identity |
| `next.config.ts` | `output: "standalone"` for Docker container build |
| `prisma/schema.prisma` | Full data model (see Data Model section below) |
| `lib/prisma.ts` | Prisma client singleton with global caching for dev hot-reload |
| `lib/auth.ts` | NextAuth v5 with MicrosoftEntraID provider + PrismaAdapter |
| `app/api/auth/[...nextauth]/route.ts` | NextAuth route handler |
| `app/api/health/route.ts` | Health endpoint — checks DB with `SELECT 1`, returns 200/503 |
| `app/layout.tsx` | Root layout with SessionProvider |
| `app/page.tsx` | Root redirect → `/dashboard` or `/auth/signin` |
| `app/auth/signin/page.tsx` | Sign-in page with "Sign in with Microsoft" button |
| `app/(dashboard)/layout.tsx` | Protected layout — redirects unauthenticated users |
| `app/(dashboard)/dashboard/page.tsx` | Engagement list for ANALYST/REVIEWER/ADMIN |
| `middleware.ts` | Route protection — redirects unauthenticated requests to `/auth/signin` |
| `Dockerfile` | Multi-stage build (deps → builder → runner); node:20-alpine; uid 1001 |
| `.env.example` | Web-specific environment variable reference |

### Dockerfile Design Decisions

- **3-stage build** (deps/builder/runner) — minimizes final image size by excluding build tools
- **`prisma migrate deploy`** runs on container start before `node server.js`
  - Idempotent: already-applied migrations are skipped
  - Ensures schema is always in sync on container restart or blue/green deploy
- **Non-root user** (`nextjs`, uid 1001) — matches security posture of `cna-api` and `cna-worker`
- **Standalone output** — Next.js copies only required files; no `node_modules` in runner stage

---

## Data Model

```
User
  id, name, email, image, role (ANALYST|REVIEWER|CLIENT|ADMIN), createdAt, updatedAt

Account, Session, VerificationToken     ← NextAuth v5 adapter tables

Engagement
  id, clientName, engagementCode, cloudProvider (AWS|AZURE|DUAL)
  status (DRAFT|DISCOVERY|ANALYSIS|REVIEW|DELIVERED)
  createdAt, updatedAt
  members → EngagementMember[]
  documents → IngestedDocument[]
  findings → Finding[]
  deliverables → Deliverable[]

EngagementMember
  userId, engagementId, role (ANALYST|REVIEWER|CLIENT|ADMIN)

IngestedDocument
  id, engagementId, filename, blobUrl
  type (CLIENT_ARCHITECTURE|COMPLIANCE_FRAMEWORK|NETWORK_DIAGRAM|CONFIGURATION_EXPORT|OTHER)
  uploadedBy, createdAt

Finding
  id, engagementId, title, description, observedState
  severity (CRITICAL|HIGH|MEDIUM|LOW|INFORMATIONAL)
  framework (CIS|NIST|ISO27001|SOC2|CUSTOM)
  reviewedBy, reviewedAt, createdAt

Deliverable
  id, engagementId, filename, blobUrl
  type (SPECIALIZATION_REPORT|EXECUTIVE_SUMMARY|TECHNICAL_FINDINGS|REMEDIATION_PLAN)
  generatedAt, createdAt
```

The `review_complete` gate from DD-009 is implemented as: `Finding.reviewedBy IS NOT NULL` on
all CRITICAL/HIGH findings before a Deliverable of type `SPECIALIZATION_REPORT` can be generated.

---

## GitHub Actions Workflows

### Renamed (Old → New)

| Old Name | New Name | Reason |
|---|---|---|
| `ci.yml` | `08-ci.yml` | Numbered sequence; CI runs after images are built |
| `release.yml` | `09-release.yml` | Numbered sequence; release is the final step |
| `cd-publish.yml` | `07-cd-publish.yml` | Numbered sequence |
| `deploy-azure-runtime.yml` | `031-deploy-azure.yml` | Renamed to reflect Terraform deploy role |

### New Workflows

| File | Purpose |
|---|---|
| `000-bootstrap-backend.yml` | One-time: creates Azure RG + storage account for Terraform remote backend |
| `05-sync-env-from-keyvault.yml` | Pulls 5 KV secrets, generates populated `.env` as 1-day artifact |
| `06-refresh-containers.yml` | Fast `az containerapp update` — no Terraform, ~2 min per image |

### Updated Workflows

**`030-build-images.yml`** (was `build-and-publish-images.yml` / implicitly pre-existing):
- Added `apps/cna-web/**` path trigger
- Added `build-web` job: builds `cna-web` image, runs smoke test (`/api/health` returns 200 or 503)
- All three images tagged `:<sha>` and `:latest`

**`031-deploy-azure.yml`** (was `deploy-azure-runtime.yml`):
- Added `web_image` workflow input
- Added `CNA_POSTGRES_ADMIN_PASSWORD`, `CNA_ENTRA_CLIENT_SECRET`, `CNA_NEXTAUTH_SECRET` secrets
  to Terraform plan/apply `-var` arguments
- Added `CNA_ENTRA_CLIENT_ID`, `CNA_NEXTAUTH_URL` variables to plan/apply
- Updated drift detection job to pass same new variables

---

## Key Design Constraints Preserved

All design contracts from documents 01–38 remain in force:

- **DD-002:** `observed_state` hedge detection — unchanged in Python engine
- **DD-003:** offline AI fallback — `AZURE_OPENAI_ENDPOINT` still optional; offline recommendations
  used if unset
- **DD-009:** `review_complete` gate — enforced at `Finding.reviewedBy` level in Prisma schema
- **DD-013:** deliverable staleness via SHA-256 — preserved in `DeliverableManifest`
- **DD-017:** ISO-timestamp filenames — preserved in `RenderPipeline`
- **DD-019:** 90-day retention — preserved in `RetentionEngine`
- **OIDC-only CI/CD** — no long-lived keys; all three Azure workflows use federated credentials
- **GHCR registry** — no ACR provisioned; Container Apps pull from GHCR via system-assigned
  managed identity

---

## Dependency Order (Terraform Applies)

```
network → identity → storage → ai
                ↓
            security  ←─── compute (web/api/worker FQDNs)
                ↓
            database  ←─── security.postgres_private_dns_zone_id
                ↓
            runtime   ←─── database (database_url), security (key_vault_id)
                ↓
         presentation
```

No circular dependencies. Terraform resolves the correct apply order from resource references.

---

*Maintained by Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert*
