# CNA Platform — GitHub Actions Workflows

> Updated 2026-04-14 · Alpha complete · Entering Beta

---

## Execution Order

```
000 → (one-time)  Create workload RG, create tfstate RG/backend, import app RG into state
010 → (manual)    Validate all GitHub Secrets, Variables, and Azure OIDC access
011 → (manual)    Pull secrets from Key Vault → .env artifact (validation)
012 → (manual)    Fast image refresh without Terraform (code-only deploys)
020 → (on push)   CI — secret scan, lint, test, Docker build
021 → (on tag)    Release — git tag → GHCR semver tag + GitHub Release
022 → (manual)    Publish — deliver reports to client portals
030 → (on push)   Build & publish all three container images to GHCR
031 → (manual)    Deploy Azure infrastructure + containers via Terraform
032 → (manual)    Teardown Azure environment with DESTROY safety gate
```

---

## Naming Conventions

All Azure resources follow the pattern `{abbreviation}-{project}-{environment}-{region}`.

| Layer | Region | `name_prefix` | Resource Group |
| --- | --- | --- | --- |
| dev | South Central US (`southcentralus`) | `cna-dev-scus` | `rg-cna-dev-scus` |
| prod | South Central US (`southcentralus`) | `cna-prod-scus` | `rg-cna-prod-scus` |

Terraform state lives in its own convention-based RG so the workload RG stays dedicated to the application stack.
Workflow 000 creates the workload RG first, then creates the backend storage account and container in the tfstate RG:

| Resource | Name | Notes |
| --- | --- | --- |
| Workload RG | `rg-cna-dev-scus` / `rg-cna-prod-scus` | Holds only the application stack |
| Tfstate RG | `rg-cna-dev-scus-tfstate` / `rg-cna-prod-scus-tfstate` | Dedicated to Terraform backend resources |
| Storage Account | `stcnatfstate0001` | Backend storage account; override only if the name is unavailable |
| Blob Container | `tfstate` | State files keyed by environment: `dev.terraform.tfstate`, `prod.terraform.tfstate` |

Terraform continues to own the workload RG after bootstrap because workflow 000 imports it into state:

| Environment | Resource Group |
| --- | --- |
| dev | `rg-cna-dev-scus` |
| prod | `rg-cna-prod-scus` |

See the GitHub Wiki page `Architecture 40 Naming Conventions` for the full reference.

---

## Workflows

### `000-bootstrap-backend.yml` — Bootstrap Workload RG and Terraform Backend

**Trigger:** Manual (run once before anything else)
**Duration:** ~2 minutes

Creates the workload resource group, creates the tfstate resource group and backend storage inside it, initializes the selected environment backend, and imports the workload RG into Terraform state.
Uses OIDC — no client secret required.

**Inputs (with defaults):**

| Input | Default | Notes |
| --- | --- | --- |
| `environment` | `dev` | Terraform environment state to initialize (`dev` or `prod`) |
| `location` | `southcentralus` | Azure region for workload RG and tfstate resources |
| `region_short` | `scus` | Used to derive the workload RG name as `rg-cna-<environment>-<region_short>` |
| `tfstate_resource_group` | _blank_ | Optional override; default resolves to `rg-cna-<environment>-<region_short>-tfstate` |
| `tfstate_storage_account` | `stcnatfstate0001` | Must be globally unique, 3–24 chars, lowercase |
| `tfstate_container` | `tfstate` | Blob container for state files |

Bootstrap result:

- Workload RG exists before first deploy
- Tfstate RG exists separately from the application RG
- Terraform backend exists in Azure Storage
- The selected state key (`dev.terraform.tfstate` or `prod.terraform.tfstate`) tracks the imported workload RG

After this runs, set these GitHub **Repository Variables**:

| Variable | Value |
| --- | --- |
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-dev-scus-tfstate` or `rg-cna-prod-scus-tfstate` |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate0001` |
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
| `frontdoor_endpoint_host_name` | Confirm `CNA_NEXTAUTH_URL` was auto-updated; update Entra redirect URI |
| `key_vault_name` | Update `KEY_VAULT_NAME` variable (replace `none`) |
| `application_insights_name` | Update `APPLICATION_INSIGHTS_NAME` variable (replace `none`) |

**Required GitHub Secrets:**

| Secret | Description |
| --- | --- |
| `AZURE_CLIENT_ID` | OIDC app registration Client ID (federated credential) |
| `AZURE_TENANT_ID` | Azure AD tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `GHCR_PAT` | GitHub PAT with `read:packages` for Container Apps image pulls |
| `CNA_POSTGRES_ADMIN_PASSWORD` | PostgreSQL admin password (min 8 chars, mixed case + special) |
| `CNA_ENTRA_CLIENT_SECRET` | Entra ID OAuth2 client secret for NextAuth |
| `CNA_NEXTAUTH_SECRET` | NextAuth JWT signing secret (`openssl rand -base64 32`) |
| `CNA_CREDENTIAL_ENCRYPTION_KEY` | Encryption key for stored customer cloud credentials |

**Required GitHub Repository Variables:**

| Variable | Initial Value | Notes |
| --- | --- | --- |
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-dev-scus-tfstate` or `rg-cna-prod-scus-tfstate` | Set after running workflow 000 |
| `TFSTATE_STORAGE_ACCOUNT` | chosen global name, e.g. `stcnatfstate0001` | Set after running workflow 000 |
| `TFSTATE_CONTAINER` | `tfstate` | Set after running workflow 000 |
| `CNA_ENTRA_CLIENT_ID` | `<app registration client ID>` | From Azure Entra app registration |
| `CNA_NEXTAUTH_URL` | `none` | Placeholder — update after first Terraform deploy |
| `CNA_AI_ENGINE_DEFAULT` | `foundry-claude` | Default engine if the database setting `ai.activeEngine` does not exist |
| `FOUNDRY_CLAUDE_ENDPOINT` | `none` | Terraform-injected private Foundry Claude Messages API endpoint used by managed identity-based runtime calls |
| `FOUNDRY_CLAUDE_MODEL` | `claude-sonnet-4-6` | Foundry Claude model id injected into cna-web |
| `CNA_AZURE_MCP_ENDPOINT` | `none` | Azure MCP server endpoint surfaced on the AI Engine page |
| `CNA_AZURE_MCP_TRANSPORT` | `sse` | Azure MCP server transport |
| `CNA_AWS_MCP_ENDPOINT` | `none` | AWS MCP server endpoint surfaced on the AI Engine page |
| `CNA_AWS_MCP_TRANSPORT` | `stdio` | AWS MCP server transport |
| `CNA_DRAWIO_MCP_URL` | `none` | draw.io MCP endpoint surfaced on the AI Engine page |

Azure AI Foundry is the Terraform-managed GenAI provider. Post-deploy
validation must confirm the Foundry Messages API host resolves through the
private endpoint path from inside the CNA VNet and that managed identity can
invoke Claude without local authentication or API-key fallback. Azure OpenAI is
optional and out-of-band unless it is later implemented as a first-class
Terraform provider with its own private networking, RBAC, deployment, and app
environment variables.
| `APPLICATION_INSIGHTS_NAME` | `none` | Replace after Terraform creates it |
| `KEY_VAULT_NAME` | `none` | Replace after Terraform creates it |

> ⚠️ `APPLICATION_INSIGHTS_NAME` and `KEY_VAULT_NAME` must be `none` (not blank) until
> Terraform creates them. Workflow 031 has skip guards for steps that depend on these values.

---

## First Deployment Checklist

```
[ ] 1. Run the interactive setup script from the repo root:
       .\scripts\Initialize-CnaGitHubSecrets.ps1 -Repo "owner/repo" -Environment dev

       The script creates or reuses the Entra app registration, configures GitHub OIDC,
       prompts for required secrets, generates supported secrets when requested, and
       writes the GitHub Actions secrets and variables used by the workflows.

[ ] 2. Run workflow 000 — Bootstrap workload RG + Terraform backend (one-time per environment, ~3 min)
       For dev, defaults are pre-filled.
       For prod, set environment=prod and verify the resolved workload RG and tfstate RG names before running.
       Update the three TFSTATE_* variables from the workflow summary.

[ ] 3. Run workflow 010 — Validate Prerequisites (~1 min)
       Confirms all secrets, variables, OIDC, and role assignments are green.

[ ] 4. Push to main — workflow 030 auto-builds all three container images (~8 min)
       OR run workflow 030 manually.

[ ] 5. Run workflow 031 (environment: dev) — first Terraform deploy (~20 min)
       Note the three Terraform outputs from the workflow summary:
         frontdoor_endpoint_host_name → your live public URL
         key_vault_name               → replace KEY_VAULT_NAME variable
         application_insights_name    → replace APPLICATION_INSIGHTS_NAME variable

[ ] 6. Confirm workflow 031 updated the GitHub Variables and then update Entra redirect URI:
       - CNA_NEXTAUTH_URL           = https://<frontdoor_endpoint_host_name>
       - KEY_VAULT_NAME             = <key_vault_name>
       - APPLICATION_INSIGHTS_NAME  = <application_insights_name>
       - Entra App redirect URI     = https://<frontdoor_endpoint_host_name>/api/auth/callback/microsoft-entra-id

[ ] 7. Run workflow 031 again — applies the corrected NEXTAUTH_URL to cna-web (~5 min)

[ ] 8. Run workflow 011 — validate all Key Vault secrets are populated

[ ] 9. Navigate to https://<frontdoor_endpoint_host_name> — sign in with Entra ID
```
