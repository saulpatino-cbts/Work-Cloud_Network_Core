# CNA Platform — GitHub Actions Workflows

## Execution Order

```
01 → (one-time)  Bootstrap Terraform backend in Azure
02 → (on push)   Build & publish all three container images to GHCR
03 → (manual)    Deploy Azure infrastructure + containers via Terraform
05 → (manual)    Pull secrets from Key Vault → .env artifact
06 → (manual)    Fast image refresh without Terraform (code-only deploys)
07 → (on push)   Deliver reports to client portals
08 → (on push)   CI — lint, test, secret scan
09 → (on tag)    Release — tag → GHCR + GitHub Release
```

---

## Workflows

### `01-bootstrap-backend.yml` — Bootstrap Terraform Backend
**Trigger:** Manual (run once before anything else)
**Duration:** ~2 minutes

Creates the Azure Resource Group + Storage Account used as the Terraform
remote backend (`azurerm` backend).

After this runs, set these GitHub **Variables** in the repo settings:

| Variable | Example Value |
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

**Required GitHub Variables:**

| Variable | Description |
|---|---|
| `TFSTATE_RESOURCE_GROUP` | Terraform state resource group |
| `TFSTATE_STORAGE_ACCOUNT` | Terraform state storage account |
| `TFSTATE_CONTAINER` | Terraform state blob container |
| `CNA_ENTRA_CLIENT_ID` | Entra ID application client ID |
| `CNA_NEXTAUTH_URL` | Canonical URL of the deployed web app |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | OpenAI model deployment name |
| `APPLICATION_INSIGHTS_NAME` | App Insights resource name (for health queries) |
| `KEY_VAULT_NAME` | Key Vault name (exported from Terraform) |

---

### `05-sync-env-from-keyvault.yml` — Sync Env from Key Vault
**Trigger:** Manual
**Duration:** ~1 minute

Pulls all platform secrets from Azure Key Vault and generates a populated
`.env` file as a **1-day workflow artifact**. Use this to validate that all
secrets are in place after an infrastructure deploy.

⚠️ The artifact contains secrets. Download it immediately — it expires after 24 hours.

---

### `06-refresh-containers.yml` — Refresh Containers (Fast Redeploy)
**Trigger:** Manual
**Duration:** ~2 minutes

Updates one or more Container App images without running Terraform.
Use this for code-only deploys where infrastructure has not changed.

Specify one or more image references:
- `api_image` → updates `cna-api`
- `worker_image` → updates `cna-worker`
- `web_image` → updates `cna-web`

After updating `cna-web`, automatically polls `/api/health` to confirm the
new revision is healthy.

---

### `07-cd-publish.yml` — CD Publish
**Trigger:** Push to `main`
**Duration:** Varies

Delivers reports and assets to client portals (Azure Blob + CDN or other targets).

---

### `08-ci.yml` — CI (Lint + Test + Scan)
**Trigger:** Push to `main`, pull requests
**Duration:** ~5 minutes

Runs the full CI pipeline:
- Python: `ruff`, `mypy`, `pytest`
- Next.js: `eslint`, `npm run build`
- Secret scanning

---

### `09-release.yml` — Release
**Trigger:** Git tag (`v*`)
**Duration:** ~5 minutes

Publishes a GitHub Release and tags GHCR images with the semver tag.

---

## First Deployment Checklist

```
[ ] 1. Create Entra ID App Registration in Azure Portal (or az CLI):
       - Redirect URI: https://<your-domain>/api/auth/callback/microsoft-entra-id
         (use a placeholder like https://cna.example.com for now; update after step 6)
       - Grant: openid, profile, email, User.Read
       - Note the Application (Client) ID and create a Client Secret

[ ] 2. Create a GitHub PAT for GHCR image pulls:
       - Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
       - New token: Expiration = 90 days (or "No expiration" for infra tokens)
       - Scope: read:packages (only — minimum required)
       - Copy the token — you cannot view it again

[ ] 3. Set all GitHub Secrets in Settings → Secrets and variables → Actions → Secrets:
       - AZURE_CLIENT_ID
       - AZURE_TENANT_ID
       - AZURE_SUBSCRIPTION_ID
       - CNA_POSTGRES_ADMIN_PASSWORD   (e.g. generate with: openssl rand -base64 16)
       - CNA_ENTRA_CLIENT_SECRET       (from step 1)
       - CNA_NEXTAUTH_SECRET           (generate with: openssl rand -base64 32)
       - GHCR_PAT                      (from step 2)

[ ] 4. Set all GitHub Variables in Settings → Secrets and variables → Actions → Variables:
       - TFSTATE_RESOURCE_GROUP        (e.g. rg-cna-tfstate)
       - TFSTATE_STORAGE_ACCOUNT       (e.g. stcnatfstate — globally unique, lowercase)
       - TFSTATE_CONTAINER             (e.g. tfstate)
       - CNA_ENTRA_CLIENT_ID           (Application Client ID from step 1)
       - CNA_NEXTAUTH_URL              (use https://cna.example.com as placeholder — update after step 6)
       - CNA_AZURE_OPENAI_DEPLOYMENT   (e.g. gpt-4o — from your Azure OpenAI deployment)
       - APPLICATION_INSIGHTS_NAME     (leave blank for now; Terraform creates it, update after step 6)
       - KEY_VAULT_NAME                (leave blank for now; Terraform creates it, update after step 6)

[ ] 5. Set up OIDC federated credential on the Entra app registration:
       az ad app create --display-name "cna-github-oidc"
       # Note the appId, then create a service principal:
       az ad sp create --id <appId>
       # Assign Contributor on subscription (or specific RG):
       az role assignment create --role Contributor --assignee <appId> --scope /subscriptions/<subId>
       # Add federated credential for GitHub Actions:
       az ad app federated-credential create --id <appId> --parameters '{
         "name": "cna-github-main",
         "issuer": "https://token.actions.githubusercontent.com",
         "subject": "repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main",
         "audiences": ["api://AzureADTokenExchange"]
       }'
       # The appId is your AZURE_CLIENT_ID secret

[ ] 6. Run workflow 01 to bootstrap the Terraform backend (one-time, ~2 min)

[ ] 7. Push to main — workflow 02 auto-builds all three container images (~8 min)
       OR run workflow 02 manually

[ ] 8. Run workflow 03 (environment: dev) — first Terraform deploy (~20 min)
       - PostgreSQL provisioning is the slow part (~10 min alone)
       - After apply completes, note the Terraform outputs:
           frontdoor_endpoint_host_name  → your public URL
           key_vault_name                → update KEY_VAULT_NAME variable
           application_insights_name     → update APPLICATION_INSIGHTS_NAME variable

[ ] 9. Update GitHub Variables with the real values from step 8:
       - CNA_NEXTAUTH_URL = https://<frontdoor_endpoint_host_name>
       - KEY_VAULT_NAME   = <key_vault_name from outputs>
       - APPLICATION_INSIGHTS_NAME = <appinsights_name from outputs>

[ ] 10. Update the Entra App Registration redirect URI with the real Front Door hostname:
        https://<frontdoor_endpoint_host_name>/api/auth/callback/microsoft-entra-id

[ ] 11. Run workflow 03 again — applies the corrected NEXTAUTH_URL to cna-web (~5 min)

[ ] 12. Run workflow 05 to validate all secrets are present in Key Vault

[ ] 13. Navigate to https://<frontdoor_endpoint_host_name> — sign in with Entra ID
```
