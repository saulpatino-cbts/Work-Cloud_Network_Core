# CNA Platform — Active TODO

> **Status as of 2026-03-08**
> All six delivery phases (A–F) are signed off and closed.
> See `documentation/phase-reviews/phase-critiques-and-sign-offs.md` for the permanent record.
> This file tracks the remaining path to first live deployment.

---

## Where We Are

| Layer | Status |
|---|---|
| Platform architecture | ✅ Complete |
| Terraform modules (networking, compute, AI, delivery, security) | ✅ Complete |
| Python backend (discovery, AI, report, delivery engines) | ✅ Complete |
| cna-web (Next.js 15, auth, dashboard) | ✅ Complete |
| GitHub Actions workflows (01–09) | ✅ Complete |
| Naming conventions (Azure CAF + region) | ✅ Complete — `{abbrev}-cna-{env}-scus` |
| Entra app registration + OIDC federation | ⏳ User action required (see Step 1) |
| First Terraform deployment (dev) | ⏳ Blocked on Step 1 |
| First container image build and push | ⏳ Blocked on Step 1 |

---

## Next Steps — First Deployment

### Step 1 — Azure + GitHub Prerequisites ⏳ IN PROGRESS

These are one-time manual steps. All automation depends on them.

**1a. Entra App Registration**
- [ ] App registration created in Azure portal
- [ ] Client secret created and stored as GitHub secret `AZURE_CLIENT_SECRET`
- [ ] App registration `client_id` stored as GitHub secret `AZURE_CLIENT_ID`
- [ ] Tenant ID stored as GitHub secret `AZURE_TENANT_ID`
- [ ] Subscription ID stored as GitHub secret `AZURE_SUBSCRIPTION_ID`

**1b. OIDC Federated Credential (replaces client secret long-term)**
- [ ] Federated credential added to the app registration
  - Issuer: `https://token.actions.githubusercontent.com`
  - Subject: `repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main`
- [ ] After OIDC is wired: remove `AZURE_CLIENT_SECRET` from GitHub secrets

**1c. GHCR PAT**
- [ ] Classic PAT created with `read:packages` scope
- [ ] Stored as GitHub secret `GHCR_PAT`

**1d. GitHub Repository Variables**
Go to repo → Settings → Secrets and variables → Actions → Variables tab → New repository variable.

| Variable | Value |
|---|---|
| `AZURE_RESOURCE_GROUP` | `rg-cna-dev-scus` _(will be created by Terraform)_ |
| `CONTAINER_REGISTRY` | `ghcr.io/saulpatinojr` |
| `KEY_VAULT_NAME` | `none` _(update after Terraform creates it)_ |
| `APPLICATION_INSIGHTS_NAME` | `none` _(update after Terraform creates it)_ |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | `gpt-4` _(or your deployment name)_ |

---

### Step 2 — Bootstrap Terraform Backend

Run workflow `01-bootstrap-backend.yml` **once**. This creates:
- Resource group `rg-cna-dev-scus` (shared RG for platform + tfstate)
- Storage account `stcnatfstate`
- Blob container `tfstate`

All defaults are pre-filled correctly — just hit **Run workflow** with `location = southcentralus`.

After it completes, set these GitHub **Repository Variables**:

| Variable | Value |
|---|---|
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-dev-scus` |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` |
| `TFSTATE_CONTAINER` | `tfstate` |

> Terraform uses `rg-cna-dev-scus` as a `data` source (pre-created by this workflow)
> rather than managing the RG itself — this prevents accidental deletion on `destroy`.

---

### Step 3 — Build and Push Container Images

Run workflow `02-build-and-publish.yml` (or it may have auto-triggered on the last push).

This builds and pushes three images to GHCR:
- `ghcr.io/saulpatinojr/cna-api:{sha}`
- `ghcr.io/saulpatinojr/cna-worker:{sha}`
- `ghcr.io/saulpatinojr/cna-web:{sha}`

**Verify in GitHub:**
- Actions tab → `02 Build and Publish` → confirm all three image jobs are green
- Packages tab → confirm three packages appear under your profile

> The image SHA tags are what Terraform references in Step 4.

---

### Step 4 — First Terraform Deploy (dev)

Run workflow `03-deploy-azure-dev.yml`.

This is the main infra deploy (~20 min). It provisions:
- VNet + subnets + NSG (`vnet-cna-dev-scus-platform`)
- Container Apps Environment (`cae-cna-dev-scus-platform`)
- Container Apps — api, worker, web (`ca-cna-dev-scus-api`, etc.)
- Key Vault (`kv-cna-dev-scus`)
- Storage account (`stcnadevscus`)
- PostgreSQL Flexible Server (`psqlf-cna-dev-scus-platform`)
- Application Insights (`appi-cna-dev-scus-platform`)
- Azure OpenAI (`aoaicnadevscus`)
- Front Door + WAF (`afd-cna-dev-scus-platform`, `afdwafcnadevscus`)
- Managed Identity (`id-cna-dev-scus-platform`)

**How to run:**
1. GitHub repo → Actions tab
2. `03 Deploy Azure Dev` → `Run workflow` → branch: `main`, environment: `dev`
3. Watch the Terraform plan step — review the plan output before it applies
4. Wait for green check (~20 min)

**After it completes:**
- Retrieve Key Vault name and App Insights name from Terraform outputs
- Update GitHub repository variables `KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME`
- Re-run workflow 03 to pick up the new values (the skip guards will now lift)

---

### Step 5 — Validate the Live Platform

After workflow 03 completes:

- [ ] Open Azure Portal → Resource Group `rg-cna-dev-scus` — all resources present
- [ ] Navigate to Front Door URL (from Terraform output `frontdoor_hostname`) — web app loads
- [ ] Sign in with Microsoft Entra — auth flow completes, dashboard loads
- [ ] Run `cna init` against the live API endpoint — engagement store created
- [ ] Check Application Insights → Live Metrics — traffic shows up

---

### Step 6 — First Real Engagement (smoke test)

- [ ] Create a test engagement via `cna init --client test-client`
- [ ] Run discovery phase: `cna discover --engagement {id} --platform aws --mock`
- [ ] Run analysis: `cna analyze --engagement {id}`
- [ ] Run report: `cna report --engagement {id} --preview`
- [ ] Verify HTML preview renders without errors

---

## Future Work (post-deployment)

| Item | Notes |
|---|---|
| Production deployment | Run workflow `03` targeting `prod` environment after dev is stable |
| JA (Japanese) language toggle | `ja_review_complete` flag — requires translated glossary review |
| MCP server wiring | `cna/modules/*/module.yaml` specifies servers — needs live MCP endpoints |
| PPTX executive deck review | Template structure signed off; validate with real findings data |
| Client portal hardening | Retention engine (90 days), SAS token TTL |
| Pre-commit hook enforcement | `detect-secrets` + `gitleaks` gates active; monitor for false positives |

---

## Useful Reference

| Document | Path |
|---|---|
| Phase sign-offs | `documentation/phase-reviews/phase-critiques-and-sign-offs.md` |
| Naming conventions | `documentation/architecture/40-naming-conventions.md` |
| Azure infra reference | `documentation/architecture/38-azure-infra-deployment-reference.md` |
| Platform architecture | `documentation/architecture/39-platform-architecture-revised.md` |
| OIDC setup blog post | `Personal-Site_HCW/content/blog/2026-03-08-github-actions-azure-oidc-no-secrets.md` |
| Secrets vs Variables | `Personal-Site_HCW/content/blog/2026-03-08-github-actions-secrets-vs-variables.md` |
