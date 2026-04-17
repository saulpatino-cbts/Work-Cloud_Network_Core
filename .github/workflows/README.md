# CNA Platform — GitHub Actions Workflows

> Updated 2026-04-14 · Alpha complete · Entering Beta

---

## Execution Order

```
000 → (one-time)  Bootstrap Terraform backend in Azure
010 → (manual)    Validate all GitHub Secrets, Variables, and Azure OIDC access
011 → (manual)    Pull secrets from Key Vault → .env artifact (validation)
012 → (manual)    Fast image refresh without Terraform (code-only deploys)
020 → (on push)   CI — secret scan, lint, test, Docker build
021 → (on tag)    Release — git tag → GHCR semver tag + GitHub Release
022 → (manual)    Publish — deliver reports to client portals
030 → (on push)   Build & publish all three container images to GHCR
031 → (manual)    Deploy Azure infrastructure + containers via Terraform
```

---

## Naming Conventions

All Azure resources follow the pattern `{abbreviation}-{project}-{environment}-{region}`.

| Layer | Region | `name_prefix` | Resource Group |
| --- | --- | --- | --- |
| dev | South Central US (`southcentralus`) | `cna-dev-scus` | `rg-cna-dev-scus` |
| prod | South Central US (`southcentralus`) | `cna-prod-scus` | `rg-cna-prod-scus` |

Terraform state resources are isolated in their own dedicated RG, separate from workload resources.
Workflow 000 creates this RG; it is never touched by Terraform destroy:

| Resource | Name | Notes |
| --- | --- | --- |
| Terraform State RG | `rg-cna-tfstate` | Dedicated to state only — never destroyed by Terraform |
| Storage Account | `stcnatfstate` | Single backend serving dev + prod state files |
| Blob Container | `tfstate` | State files keyed by environment: `dev.terraform.tfstate`, `prod.terraform.tfstate` |

Workload RGs are created and managed by Terraform (workflow 031):

| Environment | Resource Group |
| --- | --- |
| dev | `rg-cna-dev-scus` |
| prod | `rg-cna-prod-scus` |

See `documentation/architecture/40-naming-conventions.md` for the full reference.

---

## Workflows

### `000-bootstrap-backend.yml` — Bootstrap Terraform Backend

**Trigger:** Manual (run once before anything else)
**Duration:** ~2 minutes

Creates the Azure Resource Group + Storage Account used as the Terraform remote backend.
Uses OIDC — no client secret required.

**Inputs (with defaults):**

| Input | Default | Notes |
| --- | --- | --- |
| `location` | `southcentralus` | Azure region for tfstate resources |
| `tfstate_resource_group` | `rg-cna-tfstate` | Shared backend RG (no env/region suffix) |
| `tfstate_storage_account` | `stcnatfstate` | Must be globally unique, 3–24 chars, lowercase |
| `tfstate_container` | `tfstate` | Blob container for state files |

After this runs, set these GitHub **Repository Variables**:

| Variable | Value |
| --- | --- |
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate` |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` |
| `TFSTATE_CONTAINER` | `tfstate` |

---

### `010-validate-prereqs.yml` — Validate Prerequisites

**Trigger:** Manual
**Duration:** ~1 minute
**Azure auth required:** Yes (OIDC)

Read-only validation workflow. Run this before attempting any deployment to confirm
all secrets, variables, and OIDC access are correctly wired.

Checks:

- All required GitHub Secrets are non-empty
- All required GitHub Variables are set (warns on placeholder values)
- Azure OIDC login succeeds
- Contributor and User Access Administrator roles are assigned
- Tfstate storage account exists (after workflow 000 has run)

Prints a pass/fail table to the workflow step summary.

---

### `011-sync-keys.yml` — Sync Env from Key Vault

**Trigger:** Manual
**Duration:** ~1 minute

Pulls all platform secrets from Azure Key Vault and generates a populated `.env` file
as a **1-day workflow artifact**. Use this to validate that all secrets are in place
after an infrastructure deploy.

⚠️ The artifact contains secrets. Download it immediately — it expires after 24 hours.

---

### `012-fast-redeploy.yml` — Fast Redeploy (No Terraform)

**Trigger:** Manual
**Duration:** ~2 minutes

Updates one or more Container App images without running Terraform. Use this for
code-only deploys where infrastructure has not changed.

After updating `cna-web`, automatically polls `/api/health` to confirm the new
revision is healthy before completing.

---

### `020-test-codebase.yml` — CI (Lint + Test + Scan)

**Trigger:** Push to `main`, pull requests
**Duration:** ~5 minutes

Runs the full CI pipeline:

- Secret scanning (gitleaks SARIF → Security tab)
- Python: `ruff`, `mypy`, `pytest` (matrix: 3.11 + 3.12), 80% coverage gate
- Next.js: `eslint`, `npm run build`
- Docker smoke test (verifies `/api/health` endpoint responds)

---

### `021-release-version.yml` — Release

**Trigger:** Git tag `v*.*.*`
**Duration:** ~5 minutes

Tags GHCR images with the semver tag and creates a GitHub Release.

```bash
git tag v1.0.0 && git push --tags
```

---

### `022-publish-portal.yml` — Publish Portal

**Trigger:** Manual
**Duration:** Varies

Delivers engagement reports and assets to client portals (Azure Blob or AWS S3 via OIDC).

---

### `030-build-images.yml` — Build and Push Container Images

**Trigger:** Push to `main` (when `apps/**` changes), or manual
**Duration:** ~5–10 minutes (parallel builds)

Builds and pushes three images to GHCR:

- `ghcr.io/saulpatinojr/cna-api:<sha>`
- `ghcr.io/saulpatinojr/cna-worker:<sha>`
- `ghcr.io/saulpatinojr/cna-web:<sha>`

Writes `.deployment-catalog/latest-build.json` with the SHA for workflow 031 to consume.

---

### `031-deploy-azure.yml` — Deploy Azure (Dev/Prod)

**Trigger:** Manual, or nightly schedule (drift detection)
**Duration:** ~10–20 minutes (first deploy longer; subsequent deploys faster)

Full Terraform plan + apply. Includes:

- Policy gates (fmt check, validate)
- Plan with approval gate for `prod`
- Apply and export Terraform outputs
- Post-deploy health verification (Azure Monitor + App Insights direct queries)
- Progressive Front Door rollout promotion
- Certificate renewal monitoring
- Nightly drift detection

**Terraform outputs to capture after first deploy:**

| Output | Action |
| --- | --- |
| `frontdoor_endpoint_host_name` | Set `CNA_NEXTAUTH_URL` variable; update Entra redirect URI |
| `key_vault_name` | Update `KEY_VAULT_NAME` variable (replace `none`) |
| `application_insights_name` | Update `APPLICATION_INSIGHTS_NAME` variable (replace `none`) |

**Required GitHub Secrets:**

| Secret | Description |
| --- | --- |
| `AZURE_CLIENT_ID` | OIDC app registration Client ID (federated credential) |
| `AZURE_TENANT_ID` | Azure AD tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `CNA_POSTGRES_ADMIN_PASSWORD` | PostgreSQL admin password (min 8 chars, mixed case + special) |
| `CNA_ENTRA_CLIENT_SECRET` | Entra ID OAuth2 client secret for NextAuth |
| `CNA_NEXTAUTH_SECRET` | NextAuth JWT signing secret (`openssl rand -base64 32`) |

**Required GitHub Repository Variables:**

| Variable | Initial Value | Notes |
| --- | --- | --- |
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate` | Set after running workflow 000 |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` | Set after running workflow 000 |
| `TFSTATE_CONTAINER` | `tfstate` | Set after running workflow 000 |
| `CNA_ENTRA_CLIENT_ID` | `<app registration client ID>` | From Azure Entra app registration |
| `CNA_NEXTAUTH_URL` | `none` | Placeholder — update after first Terraform deploy |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Azure OpenAI model deployment name |
| `APPLICATION_INSIGHTS_NAME` | `none` | Replace after Terraform creates it |
| `KEY_VAULT_NAME` | `none` | Replace after Terraform creates it |

> ⚠️ `APPLICATION_INSIGHTS_NAME` and `KEY_VAULT_NAME` must be `none` (not blank) until
> Terraform creates them. Workflow 031 has skip guards for steps that depend on these values.

---

## First Deployment Checklist

```
[ ] 1. Create Entra ID App Registration (Azure Portal — one-time):
       - Azure Portal → Entra ID → App registrations → New registration
       - Redirect URI: https://<placeholder>/api/auth/callback/microsoft-entra-id
         (update to real Front Door hostname after step 8)
       - API permissions: openid, profile, email, User.Read
       - Certificates & secrets → New client secret → copy the value
       - Add OIDC federated credential:
           Issuer:  https://token.actions.githubusercontent.com
           Subject: repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main

[ ] 2. Set GitHub Secrets (Settings → Secrets and variables → Actions → Secrets):
       - AZURE_CLIENT_ID              (app registration client ID)
       - AZURE_TENANT_ID              (tenant GUID)
       - AZURE_SUBSCRIPTION_ID        (subscription ID)
       - CNA_ENTRA_CLIENT_SECRET      (client secret from step 1)
       - CNA_POSTGRES_ADMIN_PASSWORD  (generate: openssl rand -base64 16)
       - CNA_NEXTAUTH_SECRET          (generate: openssl rand -base64 32)

[ ] 3. Set GitHub Variables (Settings → Secrets and variables → Actions → Variables):
       - TFSTATE_RESOURCE_GROUP       = rg-cna-tfstate (set after step 4)
       - TFSTATE_STORAGE_ACCOUNT      = stcnatfstate    (set after step 4)
       - TFSTATE_CONTAINER            = tfstate          (set after step 4)
       - CNA_ENTRA_CLIENT_ID          = <app registration client ID>
       - CNA_NEXTAUTH_URL             = none             (update after step 8)
       - CNA_AZURE_OPENAI_DEPLOYMENT  = gpt-4o
       - APPLICATION_INSIGHTS_NAME    = none             (update after step 8)
       - KEY_VAULT_NAME               = none             (update after step 8)

[ ] 4. Run workflow 000 — Bootstrap Terraform Backend (one-time, ~2 min)
       All inputs are pre-filled — just run with defaults.
       Update the three TFSTATE_* variables from the workflow summary.

[ ] 5. Run workflow 010 — Validate Prerequisites (~1 min)
       Confirms all secrets, variables, OIDC, and role assignments are green.

[ ] 6. Push to main — workflow 030 auto-builds all three container images (~8 min)
       OR run workflow 030 manually.

[ ] 7. Run workflow 031 (environment: dev) — first Terraform deploy (~20 min)
       Note the three Terraform outputs from the workflow summary:
         frontdoor_endpoint_host_name → your live public URL
         key_vault_name               → replace KEY_VAULT_NAME variable
         application_insights_name    → replace APPLICATION_INSIGHTS_NAME variable

[ ] 8. Update GitHub Variables and Entra redirect URI with real values:
       - CNA_NEXTAUTH_URL           = https://<frontdoor_endpoint_host_name>
       - KEY_VAULT_NAME             = <key_vault_name>
       - APPLICATION_INSIGHTS_NAME  = <application_insights_name>
       - Entra App redirect URI     = https://<frontdoor_endpoint_host_name>/api/auth/callback/microsoft-entra-id

[ ] 9. Run workflow 031 again — applies the corrected NEXTAUTH_URL to cna-web (~5 min)

[ ] 10. Run workflow 011 — validate all Key Vault secrets are populated

[ ] 11. Navigate to https://<frontdoor_endpoint_host_name> — sign in with Entra ID
```
