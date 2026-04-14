# CNA Platform — Active TODO

> **Status as of 2026-04-14**
> Alpha stage is complete and closed. All six delivery phases (A–F) are signed off.
> The dev environment is being torn down and redeployed clean as the Alpha→Beta transition.
> This file tracks the Beta deployment checklist and post-Beta roadmap.

---

## Alpha Completed (2026-04-14)

Everything below shipped and is live on the dev environment at SHA `ace931c`.

| Feature | Status |
| --- | --- |
| Platform architecture (3-container, PostgreSQL, Entra ID) | ✅ Done |
| Terraform modules (all Azure resources) | ✅ Done |
| GitHub Actions workflows (000–031) | ✅ Done |
| Entra ID auth + OIDC federation | ✅ Done |
| First Terraform deployment (dev) | ✅ Done |
| Per-subscription sync groups (one `DiscoveryJob` per credential) | ✅ Done |
| Multi-subscription topology merge (inventory + presentations + deliverables) | ✅ Done |
| Findings count — unique issue groups vs. raw count | ✅ Done |
| Five assessment types (COMPREHENSIVE HTML + 4 Markdown) | ✅ Done |
| Comprehensive Assessment HTML output (fixed system prompt conflict) | ✅ Done |
| MS Learn enrichment (live fetch at generation time) | ✅ Done |
| Interactive Assessment: AI generation on every create/recreate | ✅ Done |
| Interactive Assessment: "View Report" + "Dashboard" split in portal | ✅ Done |
| Presentation dashboard: all pages use merged topology (fixes "1 subscription") | ✅ Done |
| Error surfacing in create-assessment-button | ✅ Done |

---

## Beta — Step 1: Fresh Environment Deployment

The dev environment resources are being deleted. Redeploy from scratch using the
sequence below. All code handles a blank Azure environment — migrations run in the
Docker migrator stage, no seed data is required.

### 1a. Verify GitHub Secrets & Variables Are Still Set

Before deploying, confirm all required values are in GitHub Settings:

**Secrets:**

| Secret | Status |
| --- | --- |
| `AZURE_CLIENT_ID` | ⚠️ Verify still valid after resource deletion |
| `AZURE_TENANT_ID` | Should be unchanged |
| `AZURE_SUBSCRIPTION_ID` | Should be unchanged |
| `CNA_POSTGRES_ADMIN_PASSWORD` | Should be unchanged |
| `CNA_ENTRA_CLIENT_SECRET` | ⚠️ Verify — Entra secret may have rotated |
| `CNA_NEXTAUTH_SECRET` | Should be unchanged |

**Variables:**

| Variable | Notes |
| --- | --- |
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate` — tfstate RG survives env deletion |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` — survives env deletion |
| `TFSTATE_CONTAINER` | `tfstate` — survives env deletion |
| `CNA_ENTRA_CLIENT_ID` | Should be unchanged |
| `CNA_NEXTAUTH_URL` | Reset to `none` until new Front Door hostname is known |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | Should be unchanged (e.g. `gpt-4o`) |
| `APPLICATION_INSIGHTS_NAME` | Reset to `none` — will be recreated by Terraform |
| `KEY_VAULT_NAME` | Reset to `none` — will be recreated by Terraform |

> The Terraform state RG (`rg-cna-tfstate`) is isolated from the workload RG
> (`rg-cna-dev-scus`) and is NOT deleted when tearing down the dev environment.
> Terraform state is preserved — the next `terraform apply` will create fresh resources
> in the workload RG rather than re-importing.

### 1b. Run Workflow 010 — Validate Prerequisites

- [ ] Run `010-validate-prereqs.yml` → confirm all secrets/variables/OIDC pass

### 1c. Build Container Images

- [ ] Push to main OR manually run `030-build-images.yml`
- [ ] Confirm three images appear in GitHub Packages (cna-api, cna-worker, cna-web)
- [ ] Note the SHA tag from the build manifest (`.deployment-catalog/latest-build.json`)

### 1d. Deploy Azure Infrastructure

- [ ] Run `031-deploy-azure.yml` (environment: `dev`)
- [ ] Watch Terraform plan output — confirm only `create` actions (no orphaned state)
- [ ] Wait for green (~20 min)
- [ ] Copy `frontdoor_endpoint_host_name` from Terraform outputs
- [ ] Update `CNA_NEXTAUTH_URL` GitHub Variable → new Front Door hostname
- [ ] Update Entra ID redirect URI → `https://<new-hostname>/api/auth/callback/microsoft-entra-id`
- [ ] Re-run `031-deploy-azure.yml` to apply the updated NextAuth URL
- [ ] Update `KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME` variables from outputs

### 1e. Validate the Live Platform

- [ ] Run `011-sync-keys.yml` → confirm all Key Vault secrets are populated
- [ ] Navigate to Front Door URL → web app loads
- [ ] Sign in with Microsoft Entra → auth flow completes, dashboard loads
- [ ] Create a test engagement → confirm DB write succeeds
- [ ] Add a cloud credential → confirm encryption/decryption works
- [ ] Run discovery → confirm per-subscription job fires, progress updates
- [ ] Check Application Insights Live Metrics → traffic shows up
- [ ] Generate at least one assessment → confirm AI content is returned and stored
- [ ] Create interactive assessment → confirm AI generation completes (~30–60 sec)
- [ ] Open presentation dashboard → confirm subscription count matches actual subscriptions synced

---

## Beta — Step 2: Beta Validation Checklist

Once the environment is up and smoke-tested, run through these scenarios:

### Discovery

- [ ] Add two or more Azure credentials to a single engagement
- [ ] Run "Re-sync all" → confirm two independent jobs appear (one per credential)
- [ ] Confirm each subscription card has its own progress bar and log
- [ ] Check inventory page → confirm both subscriptions appear merged

### Findings

- [ ] Run AI analysis after discovery → confirm findings are stored
- [ ] Check findings page header: unique-issue count should differ from raw total
- [ ] Apply severity filter → confirm "Showing X of Y issues (Z of N findings)" label updates

### Deliverables

- [ ] Generate each of the 5 assessment types individually
- [ ] Generate all assessments at once → confirm 5 deliverables created
- [ ] Open COMPREHENSIVE_ASSESSMENT → confirm it renders as HTML (not Markdown)
- [ ] Delete all deliverables → regenerate → confirm fresh AI content each time

### Interactive Assessment / Presentation

- [ ] Create interactive assessment → button shows "Generating with AI…"
- [ ] After completion, confirm "View Report" (AI HTML) AND "Dashboard" buttons appear
- [ ] Open Dashboard (presentation) → Executive page shows correct subscription count
- [ ] All 5 presentation pages load without errors (overview, executive, technical, compliance, remediation)

### Auth & Roles

- [ ] Sign in as ANALYST → can create/run engagements
- [ ] Confirm REVIEWER role can view but not trigger discovery
- [ ] Confirm CLIENT role reaches deliverables portal only

---

## Post-Beta Roadmap

| Item | Priority | Notes |
| --- | --- | --- |
| Production deployment | High | Run `031` targeting `prod` after dev Beta validation |
| AWS Provider Expansion (Phase G) | High | Azure parity; needs Phase C discovery stubs for AWS |
| Phase C: Azure network/security discovery stubs | Medium | `azure_network/security` module stubs — remaining Phase C work |
| JA (Japanese) language toggle | Low | `ja_review_complete` flag — requires translated glossary review |
| MCP server wiring | Low | `cna/modules/*/module.yaml` specifies servers — needs live MCP endpoints |
| Client portal hardening | Medium | Retention engine (90 days), SAS token TTL enforcement |
| Pre-commit hook enforcement monitoring | Ongoing | `detect-secrets` + `gitleaks` — monitor for false positives |
| Node.js Dockerfile base image SHA pin | Low | Pin `node:20-alpine@sha256:<hash>` for full supply chain compliance |
| gitleaks-action SHA pin in `020-test-codebase.yml` | Low | Currently uses `v2` tag — TODO comment exists in workflow |

---

## Useful Reference

| Document | Path |
| --- | --- |
| Phase sign-offs | `documentation/phase-reviews/phase-critiques-and-sign-offs.md` |
| Naming conventions | `documentation/architecture/40-naming-conventions.md` |
| Azure infra reference | `documentation/architecture/38-azure-infra-deployment-reference.md` |
| Platform architecture | `documentation/architecture/39-platform-architecture-revised.md` |
| Deployment guide | `documentation/deployment-guide.md` |
| Secrets reference | `documentation/secrets-reference.md` |
| Workflows guide | `documentation/workflows-guide.md` |
