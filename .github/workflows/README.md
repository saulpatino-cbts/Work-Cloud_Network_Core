# CNA Platform — GitHub Actions Workflows

## Execution Order

```
01 → (one-time)  Bootstrap Terraform backend in Azure
02 → (on push)   Build & publish all three container images to GHCR
03 → (manual)    Deploy Azure infrastructure + containers via Terraform
04 → (manual)    Pull secrets from Key Vault → .env artifact
05 → (manual)    Fast image refresh without Terraform (code-only deploys)
06 → (on push)   Deliver reports to client portals
07 → (on push)   CI — lint, test, secret scan
08 → (on tag)    Release — tag → GHCR + GitHub Release
```

---

## Naming Conventions

All Azure resources follow the pattern `{abbreviation}-{project}-{environment}-{region}`.

| Layer | Region | `name_prefix` | Resource Group |
|---|---|---|---|
| dev | South Central US (`southcentralus`) | `cna-dev-scus` | `rg-cna-dev-scus` |
| prod | South Central US (`southcentralus`) | `cna-prod-scus` | `rg-cna-prod-scus` |

Terraform state resources are isolated in their own dedicated RG, separate from workload resources.
Workflow 01 creates this RG; it is never touched by Terraform itself:

| Resource | Name | Notes |
|---|---|---|
| Terraform State RG | `rg-cna-tfstate` | Dedicated to state only — never destroyed by Terraform |
| Storage Account | `stcnatfstate` | Single backend serving dev + prod state files |
| Blob Container | `tfstate` | State files keyed by environment: `dev.terraform.tfstate`, `prod.terraform.tfstate` |

Workload RGs are created and managed by Terraform (workflow 03):

| Environment | Resource Group |
|---|---|
| dev | `rg-cna-dev-scus` |
| prod | `rg-cna-prod-scus` |

See `documentation/architecture/40-naming-conventions.md` for the full reference.

---

## Workflows

### `01-bootstrap-backend.yml` — Bootstrap Terraform Backend
**Trigger:** Manual (run once before anything else)
**Duration:** ~2 minutes
**Default region:** `southcentralus`

Creates the Azure Resource Group + Storage Account used as the Terraform
remote backend (`azurerm` backend). Uses OIDC — no client secret required.

**Inputs (with defaults):**

| Input | Default | Notes |
|---|---|---|
| `location` | `southcentralus` | Azure region for tfstate resources |
| `tfstate_resource_group` | `rg-cna-tfstate` | Shared backend RG (no env/region suffix) |
| `tfstate_storage_account` | `stcnatfstate` | Must be globally unique, 3–24 chars, lowercase |
| `tfstate_container` | `tfstate` | Blob container for state files |

After this runs, the workflow summary will display the values to set. Add these
GitHub **Repository Variables** (Settings → Secrets and variables → Actions → Variables tab):

| Variable | Value |
|---|---|
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate` |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` |
| `TFSTATE_CONTAINER` | `tfstate` |

---

### `02-build-and-publish-images.yml` — Build and Publish Images
**Trigger:** Push to `main` (when `apps/cna-api/**`, `apps/cna-worker/**`, or `apps/cna-web/**` changes), or manual
**Duration:** ~5–10 minutes (parallel builds)

Builds and pushes three images to GHCR:
- `ghcr.io/saulpatinojr/cna-api:<sha>` and `:latest`
- `ghcr.io/saulpatinojr/cna-worker:<sha>` and `:latest`
- `ghcr.io/saulpatinojr/cna-web:<sha>` and `:latest`

Also runs a smoke test on `cna-web` — verifies the process starts and
`/api/health` returns 200 or 503 (503 is expected in CI since there's no DB).

---

### `03-deploy-azure-dev.yml` — Deploy Azure (Dev/Prod)
**Trigger:** Manual
**Duration:** ~10–20 minutes (first deploy longer; subsequent deploys faster)

Full Terraform plan + apply for the specified environment. Includes:
- Policy gates (fmt check, validate)
- Plan with approval gate for `prod`
- Apply and export Terraform outputs
- Post-deploy health verification
- Drift detection (scheduled nightly)

**Terraform outputs to note after first deploy:**

| Output | Use |
|---|---|
| `frontdoor_endpoint_host_name` | → set `CNA_NEXTAUTH_URL`, update Entra redirect URI |
| `key_vault_name` | → update `KEY_VAULT_NAME` variable (replace `none`) |
| `application_insights_name` | → update `APPLICATION_INSIGHTS_NAME` variable (replace `none`) |

**Required GitHub Secrets:**

| Secret | Description |
|---|---|
| `AZURE_CLIENT_ID` | Service principal client ID (OIDC federated credential) |
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `CNA_POSTGRES_ADMIN_PASSWORD` | PostgreSQL admin password (min 8 chars, mixed case + special) |
| `CNA_ENTRA_CLIENT_SECRET` | Entra ID OAuth client secret |
| `CNA_NEXTAUTH_SECRET` | NextAuth JWT secret (`openssl rand -base64 32`) |
| `GHCR_PAT` | GitHub classic PAT with `read:packages` scope — Container Apps use this to pull GHCR images |

**Required GitHub Repository Variables:**

| Variable | Initial Value | Notes |
|---|---|---|
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate` | Set after running workflow 01 |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` | Set after running workflow 01 |
| `TFSTATE_CONTAINER` | `tfstate` | Set after running workflow 01 |
| `CNA_ENTRA_CLIENT_ID` | `<app registration client ID>` | From Azure Entra app registration |
| `CNA_NEXTAUTH_URL` | `https://cna.example.com` | Placeholder — update after first Terraform deploy |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Azure OpenAI model deployment name |
| `APPLICATION_INSIGHTS_NAME` | `none` | GitHub requires non-empty values; replace after deploy |
| `KEY_VAULT_NAME` | `none` | GitHub requires non-empty values; replace after deploy |

> ⚠️ `APPLICATION_INSIGHTS_NAME` and `KEY_VAULT_NAME` must be set to `none` (not blank) until
> Terraform creates them. Workflow 03 has skip guards for steps that use these values when
> set to `none`.

---

### `04-sync-env-from-keyvault.yml` — Sync Env from Key Vault
**Trigger:** Manual
**Duration:** ~1 minute

Pulls all platform secrets from Azure Key Vault and generates a populated
`.env` file as a **1-day workflow artifact**. Use this to validate that all
secrets are in place after an infrastructure deploy.

⚠️ The artifact contains secrets. Download it immediately — it expires after 24 hours.

---

### `05-refresh-containers.yml` — Refresh Containers (Fast Redeploy)
**Trigger:** Manual
**Duration:** ~2 minutes

Updates one or more Container App images without running Terraform.
Use this for code-only deploys where infrastructure has not changed.

Specify one or more image references:
- `api_image` → updates `ca-cna-dev-scus-api` or `ca-cna-prod-scus-api`
- `worker_image` → updates `ca-cna-dev-scus-worker` or `ca-cna-prod-scus-worker`
- `web_image` → updates `ca-cna-dev-scus-web` or `ca-cna-prod-scus-web`

After updating `cna-web`, automatically polls `/api/health` to confirm the
new revision is healthy.

---

### `06-cd-publish.yml` — CD Publish Portal
**Trigger:** Manual or `workflow_call`
**Duration:** Varies

Delivers reports and assets to client portals (Azure Blob + CDN or AWS S3 via OIDC).
Runs `cna publish run` inside the CNA container for a specified engagement.

---

### `07-ci.yml` — CNA CI (Lint + Test + Scan)
**Trigger:** Push to `main`, pull requests
**Duration:** ~5 minutes

Runs the full CI pipeline:
- Python: `ruff`, `mypy`, `pytest` (matrix: 3.11 + 3.12)
- Next.js: `eslint`, `npm run build`
- Secret scanning (gitleaks SARIF → Security tab)
- Module dependency check

---

### `08-release.yml` — Release
**Trigger:** Git tag (`v*.*.*`)
**Duration:** ~5 minutes

Publishes a GitHub Release and tags GHCR images with the semver tag.
Auto-generates changelog from PRs merged since the last tag.

---

## First Deployment Checklist

```
[ ] 1. Create Entra ID App Registration in Azure Portal (or az CLI):
       - Redirect URI: https://cna.example.com/api/auth/callback/microsoft-entra-id
         (placeholder — update to real Front Door hostname after step 8)
       - API permissions: openid, profile, email, User.Read
       - Note the Application (Client) ID and create a Client Secret

[ ] 2. Create a GitHub PAT for GHCR image pulls:
       - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
       - New token: Expiration = 90 days (or No expiration for long-lived infra tokens)
       - Scope: read:packages only (nested under write:packages — expand, check only read:packages)
       - Copy the token — you cannot view it again

[ ] 3. Set up OIDC federated credential on the Entra app registration:
       az ad sp create --id <appId>
       az role assignment create \
         --role Contributor \
         --assignee <appId> \
         --scope /subscriptions/<subscriptionId>
       az ad app federated-credential create --id <appId> --parameters '{
         "name": "cna-github-main",
         "issuer": "https://token.actions.githubusercontent.com",
         "subject": "repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main",
         "audiences": ["api://AzureADTokenExchange"]
       }'

[ ] 4. Set GitHub Secrets (Settings → Secrets and variables → Actions → Secrets tab):
       - AZURE_CLIENT_ID             (appId from step 3)
       - AZURE_TENANT_ID             (your Azure tenant ID)
       - AZURE_SUBSCRIPTION_ID       (your Azure subscription ID)
       - CNA_POSTGRES_ADMIN_PASSWORD (generate: openssl rand -base64 16)
       - CNA_ENTRA_CLIENT_SECRET     (client secret from step 1)
       - CNA_NEXTAUTH_SECRET         (generate: openssl rand -base64 32)
       - GHCR_PAT                    (PAT from step 2)

[ ] 5. Set GitHub Repository Variables (Settings → Secrets and variables → Actions → Variables tab):
       Note: GitHub does not allow empty variable values — use none as a placeholder
       where the real value is not yet known.

       - TFSTATE_RESOURCE_GROUP      = rg-cna-tfstate
       - TFSTATE_STORAGE_ACCOUNT     = stcnatfstate
       - TFSTATE_CONTAINER           = tfstate
       - CNA_ENTRA_CLIENT_ID         = <Application (Client) ID from step 1>
       - CNA_NEXTAUTH_URL            = https://cna.example.com  (placeholder)
       - CNA_AZURE_OPENAI_DEPLOYMENT = gpt-4o  (or your deployment name)
       - APPLICATION_INSIGHTS_NAME   = none    (Terraform creates this — update after step 8)
       - KEY_VAULT_NAME              = none    (Terraform creates this — update after step 8)

[ ] 6. Run workflow 01 — Bootstrap Terraform Backend (one-time, ~2 min)
       Inputs: location = southcentralus (all other inputs keep their defaults)

[ ] 7. Push to main — workflow 02 auto-builds all three container images (~8 min)
       OR run workflow 02 manually if images are not yet built

[ ] 8. Run workflow 03 (environment: dev) — first Terraform deploy (~20 min)
       - PostgreSQL provisioning is the slowest part (~10 min)
       - After apply completes, note the Terraform outputs:
           frontdoor_endpoint_host_name  → your live public URL
           key_vault_name                → replace KEY_VAULT_NAME variable
           application_insights_name     → replace APPLICATION_INSIGHTS_NAME variable
       - Dev resource names follow cna-dev-scus prefix:
           rg-cna-dev-scus, ca-cna-dev-scus-api, kv-cna-dev-scus, etc.

[ ] 9. Update GitHub Variables with the real values from step 8:
       - CNA_NEXTAUTH_URL           = https://<frontdoor_endpoint_host_name>
       - KEY_VAULT_NAME             = <key_vault_name from Terraform outputs>
       - APPLICATION_INSIGHTS_NAME  = <application_insights_name from Terraform outputs>

[ ] 10. Update Entra App Registration redirect URI with the real Front Door hostname:
        https://<frontdoor_endpoint_host_name>/api/auth/callback/microsoft-entra-id

[ ] 11. Run workflow 03 again — applies the corrected NEXTAUTH_URL to cna-web (~5 min)

[ ] 12. Run workflow 04 to validate all secrets are present in Key Vault

[ ] 13. Navigate to https://<frontdoor_endpoint_host_name> — sign in with Entra ID
```
