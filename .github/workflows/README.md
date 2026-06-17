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
030 → (on push)   Build & publish CLI plus app container images to GHCR
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
The setup script creates the workload RG using the standard naming convention, derives the tfstate names from the selected subscription, and pre-creates the tfstate resource group, storage account, and container so workflow 000 can focus on initializing Terraform state and importing the workload RG:

| Resource | Name | Notes |
| --- | --- | --- |
| Workload RG | `rg-cna-dev-scus` / `rg-cna-prod-scus` | Holds only the application stack |
| Tfstate RG | `rg-cna-dev-scus-tfstate` / `rg-cna-prod-scus-tfstate` | Dedicated to Terraform backend resources |
| ACA managed RG | `rg-cna-dev-scus-cae-managed` / `rg-cna-prod-scus-cae-managed` | Azure-managed Container Apps environment infrastructure RG, named deterministically by Terraform |
| Storage Account | `stcnatfstate0001` | Backend storage account; script derives a unique name if the default is unavailable |
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

Creates the workload resource group if needed, creates the tfstate resource group and backend storage inside it if needed, initializes the selected environment backend, and imports the workload RG into Terraform state.
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

- Workload RG exists before first deploy and may already be created by the setup script
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

Read-only validation workflow. Run this after workflow 000 and before attempting any deployment to confirm
all secrets, variables, and OIDC access are correctly wired.

Checks:

- All required GitHub Secrets are non-empty
- All required GitHub Variables are set (warns on placeholder values)
- Azure OIDC login succeeds
- Contributor and User Access Administrator roles are assigned
- Tfstate storage account exists (after workflow 000 has run)
- `Microsoft.AlertsManagement` is registered in the subscription

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

The workflow now derives the workload resource group from `TFSTATE_RESOURCE_GROUP`
by stripping the `-tfstate` suffix, so the common path does not require manually
typing `region_short`. Use the optional `resource_group` input only when you need
to override the convention-based target.

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

Notes:

- Uses the `ghcr.io/<owner>/cna` CLI image, which workflow `030` now publishes on every main build.
- Supports downloading an `engagement_artifact` into `engagements/` before publish.
- For `cloud=azure`, pass `azure_storage_account` and optionally `azure_container`.
- For `cloud=aws`, the workflow uses `CNA_PUBLISH_BUCKET`.

---

### `030-build-images.yml` — Build and Push Container Images

**Trigger:** Push to `main` (when `apps/**` changes), or manual
**Duration:** ~5–10 minutes (parallel builds)

Builds and pushes four images to GHCR:

- `ghcr.io/saulpatinojr/cna:<sha>`
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
| `frontdoor_endpoint_host_name` | Confirm `CNA_NEXTAUTH_URL` was auto-updated; Entra app homepage and redirect URI are also synced |
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
| `CNA_AZURE_MCP_ENDPOINT` | `https://mcp.azure.com` | Public Azure MCP endpoint from Microsoft Learn; override later if you wire a private endpoint |
| `CNA_AZURE_MCP_TRANSPORT` | `streamable-http` | Azure MCP transport used by the public endpoint |
| `CNA_AWS_MCP_ENDPOINT` | `https://aws-mcp.us-east-1.api.aws/mcp` | Official AWS MCP remote endpoint from the AWS Agent Toolkit docs |
| `CNA_AWS_MCP_TRANSPORT` | `streamable-http` | AWS MCP transport used by the public endpoint |
| `CNA_DRAWIO_MCP_URL` | auto-derived from `CNA_NEXTAUTH_URL` | Defaults to `<nextauth-url>/api/drawio-mcp` when a real HTTPS URL is present |

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

> Requirement: the Azure subscription must have `Microsoft.AlertsManagement` registered before the first live deploy, otherwise Application Insights smart-detection alert provisioning can fail.

---

## First Deployment Checklist

```
[ ] 1. Run the interactive setup script from the repo root:
       .\scripts\Initialize-CnaGitHubSecrets.ps1 -Repo "owner/repo" -Environment dev

       The script creates or reuses the Entra app registration, configures GitHub OIDC,
       uses existing GitHub values when present, derives standard names automatically,
       only prompts for secrets that cannot be inferred, creates the workload RG,
       prepares the tfstate backend,
       writes the GitHub Actions secrets and variables used by the workflows, and
       dispatches workflow 000 by default.

[ ] 2. Let workflow 000 — Bootstrap workload RG + Terraform backend complete (one-time per environment, ~3 min)
       For dev, the setup script dispatches it with the seeded TFSTATE_* values, the pre-created workload RG, and the pre-created backend.
       Use -SkipBootstrapDispatch on the setup script only when you intentionally want to launch 000 yourself.

[ ] 3. Run workflow 010 — Validate Prerequisites (~1 min)
       Confirms all secrets, variables, OIDC, and role assignments are green.

[ ] 4. Push to main — workflow 030 auto-builds all three container images (~8 min)
       OR run workflow 030 manually.

[ ] 5. Run workflow 031 (environment: dev) — first Terraform deploy (~20 min)
       Note the three Terraform outputs from the workflow summary:
         frontdoor_endpoint_host_name → your live public URL
         key_vault_name               → replace KEY_VAULT_NAME variable
         application_insights_name    → replace APPLICATION_INSIGHTS_NAME variable

[ ] 6. Confirm workflow 031 updated the GitHub Variables and synced the Entra app web settings:
       - CNA_NEXTAUTH_URL           = https://<frontdoor_endpoint_host_name>
       - KEY_VAULT_NAME             = <key_vault_name>
       - APPLICATION_INSIGHTS_NAME  = <application_insights_name>
       - Entra App home page URL    = https://<frontdoor_endpoint_host_name>
       - Entra App redirect URI     = https://<frontdoor_endpoint_host_name>/api/auth/callback/microsoft-entra-id

[ ] 7. Run workflow 031 again — applies the corrected NEXTAUTH_URL to cna-web (~5 min)

[ ] 8. Run workflow 011 — validate all Key Vault secrets are populated

[ ] 9. Navigate to https://<frontdoor_endpoint_host_name> — sign in with Entra ID
```
