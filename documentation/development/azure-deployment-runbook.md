# CNA Platform — Azure Deployment Runbook

> Last updated: 2026-04-12

This document covers how to deploy and update the CNA Platform on Azure — from a first-time
bootstrap through routine day-to-day releases.

---

## Workflow Numbering Scheme

Workflows are numbered to make the execution order unambiguous.

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| **000** | `000-bootstrap-backend.yml` | Manual — once ever | Creates the Terraform state storage account (`rg-cna-tfstate`) and its container |
| **010** | `010-validate-prereqs.yml` | Manual | Verifies OIDC service principal, state backend, and required GitHub secrets exist |
| **011** | `011-sync-keys.yml` | Manual | Syncs secrets from Azure Key Vault → GitHub Actions secrets |
| **012** | `012-fast-redeploy.yml` | Manual | Redeploys container images without running Terraform (image-only update) |
| **020** | `020-test-codebase.yml` | Push / PR to `main` | Lint, type-check, unit tests across all apps |
| **021** | `021-release-version.yml` | Manual / tag | Tags a release version |
| **022** | `022-publish-portal.yml` | Manual | Publishes client-facing portal artifacts |
| **030** | `030-build-images.yml` | Manual | Builds and pushes Docker images (web, api, worker) to GHCR with SHA tags |
| **031** | `031-deploy-azure.yml` | Manual | Full Terraform plan + apply + DB migrations + health verification |

---

## Prerequisites (One-Time Bootstrap)

These steps are done **once** per Azure subscription and never need to be repeated unless the
subscription or tenant changes.

### 1. Create the Terraform State Backend

Run workflow `000-bootstrap-backend`. This creates:

- Resource group: `rg-cna-tfstate`
- Storage account: configured for Terraform state blobs
- Container: one per environment (`dev`, `prod`)

The workload resource group (`rg-cna-dev-scus`, `rg-cna-prod-scus`) is **not** created here —
Terraform creates it on first `031` run. Keeping state in a separate RG means the entire workload
environment can be destroyed and rebuilt without losing state.

### 2. Configure the OIDC Service Principal

GitHub Actions authenticates to Azure using OIDC (no stored credentials). The service principal
needs:

- **Contributor** on the subscription (for Terraform to create all resources)
- **User Access Administrator** on the subscription (for Terraform to create role assignments)
- A federated credential pointing at the GitHub repo and branch

Set these GitHub repository secrets:

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | Service principal application (client) ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Target subscription ID |

### 3. Set Application Secrets

These secrets are consumed by Terraform to wire secrets into the Container Apps and Key Vault.

| Secret / Variable | Where | Description |
|---|---|---|
| `CNA_POSTGRES_ADMIN_PASSWORD` | GitHub secret | PostgreSQL admin password |
| `CNA_ENTRA_CLIENT_SECRET` | GitHub secret | Entra ID app registration client secret |
| `CNA_NEXTAUTH_SECRET` | GitHub secret | Auth.js v5 signing key (run `openssl rand -base64 32`) |
| `CNA_CREDENTIAL_ENCRYPTION_KEY` | GitHub secret | Encryption key for stored customer credentials |
| `CNA_ENTRA_CLIENT_ID` | GitHub variable | Entra ID app registration client ID |
| `CNA_NEXTAUTH_URL` | GitHub variable | Public URL of the web app (e.g. `https://cna.yourdomain.com`) |
| `GHCR_PAT` | GitHub secret | GitHub personal access token with `read:packages` for pulling images |
| `TFSTATE_RESOURCE_GROUP` | GitHub variable | `rg-cna-tfstate` |
| `TFSTATE_STORAGE_ACCOUNT` | GitHub variable | State storage account name |
| `TFSTATE_CONTAINER` | GitHub variable | State container name |

Run workflow `010-validate-prereqs` to verify all of the above are present before proceeding.

---

## First Deployment (Empty State)

When Terraform state does not exist for an environment, `031` provisions everything from scratch.

### Step 1 — Build Images

Run `030-build-images`. This builds all three application containers from the current `main`
branch and pushes them to GHCR:

```
ghcr.io/saulpatinojr/cna-web:<SHA>
ghcr.io/saulpatinojr/cna-api:<SHA>
ghcr.io/saulpatinojr/cna-worker:<SHA>
```

**Always use SHA-tagged images, not `:latest`.** SHA tags are immutable — `:latest` can silently
pull a different image between plan and apply, breaking the release audit trail.

Copy the three SHA image references from the workflow output.

### Step 2 — Deploy Infrastructure + Application

Run `031-deploy-azure` with:
- **Environment:** `dev` (first) or `prod`
- **api_image / worker_image / web_image:** paste the SHA-tagged references from Step 1
- **deploy_mode:** `release`

#### What Terraform provisions on a clean state

Every resource below is created by a single `terraform apply`. Nothing requires manual portal
clicks.

| Layer | Resources Created | Terraform Source |
|---|---|---|
| **Networking** | Resource group, VNet (`10.40.0.0/16` dev / `10.50.0.0/16` prod), 3 subnets (ACA infra, private endpoints, database) | `main.tf` inline |
| **Storage** | Storage account, two blob containers (`raw-artifacts`, `deliverables`), lifecycle management rules (move to Cool, auto-delete) | `module.storage` |
| **Identity** | User-assigned managed identity, Key Vault with soft-delete and purge protection | `module.identity` |
| **Compute** | Container Apps environment (VNet-integrated), Container Apps for `cna-web`, `cna-api`, `cna-worker`, Log Analytics workspace | `module.compute` |
| **AI** | Azure OpenAI account, model deployment (`gpt-5.2`), Application Insights | `module.ai` |
| **Database** | PostgreSQL Flexible Server (VNet-delegated, private DNS, no public endpoint) | `module.database` |
| **Security** | Private DNS zones, private endpoints (storage, Key Vault), Azure Front Door profile + endpoint + route | `module.security` |
| **Runtime wiring** | Key Vault secrets (DATABASE_URL, NEXTAUTH_SECRET, ENTRA_CLIENT_SECRET), RBAC role assignments (Storage Blob Data Contributor, Cognitive Services OpenAI User) for each Container App | `module.runtime` + inline `azurerm_role_assignment` |

All Container Apps authenticate to Azure services (OpenAI, Storage, Key Vault) via
`DefaultAzureCredential` using system-assigned managed identity — no connection strings or API
keys in application code.

#### After Terraform apply

The workflow automatically:

1. **Runs database migrations** — creates a one-shot Container App job that executes
   `prisma migrate deploy` against the PostgreSQL Flexible Server, then deletes the job.
2. **Waits for Container Apps to stabilize** — polls the Front Door endpoint until the app
   responds (HTTP 200/302/401/403 accepted).
3. **Verifies Azure Monitor health** — queries `OriginHealthPercentage` on the Front Door profile;
   must meet the 95% threshold before the workflow passes.

---

## Routine Release (Subsequent Deployments)

The same two-workflow sequence applies every time code changes are deployed.

```
030-build-images  →  031-deploy-azure (release mode)
```

Only the layers that changed will be updated by Terraform. If only application code changed
(no IaC changes), Terraform still runs but produces no infrastructure changes — it only updates
the Container App image references.

### Fast Redeploy (Image-Only)

If you need to push a new image without running Terraform at all (e.g. a hotfix), use
`012-fast-redeploy`. This calls `az containerapp update` directly on each Container App — faster
than a full Terraform cycle, but skips the Terraform plan/apply entirely. Use sparingly; all
production changes should normally go through `031` so Terraform state stays authoritative.

---

## Rollback

If a deployment causes a regression:

1. Run `031-deploy-azure` with `deploy_mode: rollback`
2. Paste the previous release's SHA-tagged image references into `previous_api_image` /
   `previous_worker_image`

The workflow resolves the rollback targets from the `.deployment-catalog/` release catalog if
previous image references are left blank.

---

## Environment Differences

| Setting | dev | prod |
|---|---|---|
| VNet address space | `10.40.0.0/16` | `10.50.0.0/16` |
| Storage replication | LRS (cheapest) | ZRS (zone-resilient) |
| Scale to zero | Enabled (no charge at idle) | Disabled (avoids cold-start SLA impact) |
| Log retention | 30 days | 90 days (compliance) |
| Key Vault soft-delete | 7 days | 90 days |
| Database SKU | Default (Burstable) | `GP_Standard_D2s_v3` — 2 vCores, 8 GB RAM |
| Database storage | Default | 64 GB |
| Database backup | Default | 30 days, geo-redundant |
| Container Apps LB | External (public) | Internal (traffic via Front Door only) |
| OpenAI model | `gpt-5.2` | `gpt-5.2` |

---

## Idempotency Notes

`031` is designed to be re-run safely at any time:

- The `state mv` step (rename of the Azure OpenAI cognitive deployment resource in Terraform
  state) runs with `|| true` — it silently skips if the resource is already correctly named.
- Role assignment imports run with `|| true` — they skip if the assignment is already in state.
- `terraform apply` is always run against the plan generated in the same workflow run — stale
  plan conflicts are not possible.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `409 RoleAssignmentExists` | Role assignment exists in Azure but not in Terraform state | The import step in `plan` should have caught this; check the import step logs for silent failures |
| `SpecialFeatureOrQuotaIdRequired` on OpenAI deployment | Subscription lacks quota for the requested model | Request quota access in Azure portal → Cognitive Services → Quotas; fall back to `gpt-4o` in `module "ai"` block as interim |
| Container App 503 after deploy | Cold start or image pull delay | Wait 2-3 minutes; `012-fast-redeploy` can force a restart |
| Migration job times out | Database unreachable from Container Apps environment | Verify PostgreSQL subnet delegation and private DNS zone link in `module.security` |
| `No value for required variable` during `terraform import` | Import step missing `TF_VAR_*` env block | All declared sensitive variables must be satisfied even for unrelated resources |
