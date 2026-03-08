# 38 — Azure Infrastructure Deployment Reference

**Date:** 2026-03-07
**Author:** Saul Patino Jr.
**Status:** Active — applies to all Azure infra work going forward

---

## Purpose

This document captures the Azure deployment pattern validated in `MVP-Azure_Spec_Builder`
and maps it directly to the CNA platform. It is the authoritative reference for:

- Which Azure resources CNA provisions and why
- How the GitHub Actions workflows sequence (and how to avoid common cycles)
- The complete secrets and variables checklist before first deployment
- Key differences from the Spec Builder pattern

Read this before touching any Terraform or workflow file.

---

## Validated Pattern: MVP-Azure_Spec_Builder

The Spec Builder runs a containerized Next.js app on Azure Container Apps behind
Azure Front Door with private networking. Its deployment pattern, refined through
multiple real deployments, is the direct basis for CNA's Azure infra.

**Spec Builder resource stack (for reference):**
- Container Apps Environment (VNet-delegated subnet, internal load balancer)
- Azure Container Registry (ACR) for image storage
- PostgreSQL Flexible Server (private, VNet-integrated)
- Azure Blob Storage (evidence files + static portal)
- Azure Key Vault (secrets at runtime)
- Application Insights + Log Analytics
- Azure OpenAI (Cognitive Services, S0 SKU)
- Azure Front Door Standard (WAF + CDN profile)
- Private Endpoints: blob, Key Vault, OpenAI, PostgreSQL
- Private DNS Zones linked to VNet
- User-assigned Managed Identity (secrets access)
- OIDC App Registration (GitHub Actions → Azure, no long-lived keys)
- Terraform remote backend (Storage Account blob container)

---

## CNA Resource Stack

CNA follows the same topology with two differences:

1. **No database.** Engagement data lives in blob storage (engagements container)
   and local disk during an engagement run. No PostgreSQL needed.
2. **GHCR instead of ACR.** Images are published to GitHub Container Registry via
   `build-and-publish-images.yml`. No ACR is provisioned — Container Apps pull
   from GHCR using SystemAssigned managed identity.

**CNA Azure resources:**

| Resource | Terraform module | Notes |
|---|---|---|
| Resource Group | `environments/azure/{env}/main.tf` | `rg-cna-platform-{env}-eus` |
| Virtual Network (10.40.0.0/16) | `main.tf` | Platform VNet |
| Subnet: ACA infra (10.40.0.0/23) | `main.tf` | Delegated to `Microsoft.App/environments` |
| Subnet: Private endpoints (10.40.2.0/24) | `main.tf` | Private endpoint landing zone |
| Container Apps Environment | `providers/azure/compute` | Internal LB, VNet-integrated |
| Container App: cna-api | `providers/azure/compute` | SystemAssigned identity, GHCR pull |
| Container App: cna-worker | `providers/azure/compute` | SystemAssigned identity, GHCR pull |
| Log Analytics Workspace | `providers/azure/compute` | Feeds Application Insights |
| Storage Account (StorageV2, LRS) | `providers/azure/storage` | Delivery portal + engagements blob |
| Blob containers: engagements, reports | `providers/azure/storage` | Private access |
| Static website (Storage) | `providers/azure/storage` | Client portal HTML |
| CDN Profile + Endpoint | `providers/azure/presentation` | Standard_Microsoft SKU |
| Azure Key Vault (Standard) | `providers/azure/identity` | 7-day soft delete |
| User-assigned Managed Identity | `providers/azure/identity` | Secret access + blob access |
| Application Insights | `providers/azure/ai` | `application_type = "other"` |
| Azure OpenAI (Cognitive, S0) | `providers/azure/ai` | Optional — Phase D enrichment |
| NSG: platform | `providers/azure/security` | Allow 443 inbound from allowed CIDRs |
| Private DNS: blob, keyvault, openai | `providers/azure/security` | VNet-linked |
| Private Endpoints: blob, keyvault, openai | `providers/azure/security` | Resolves via private DNS |
| Azure Front Door Standard (WAF) | `providers/azure/security` | Prevention mode, DefaultRuleSet |
| RBAC: Storage Blob Data Contributor | `providers/azure/runtime` | Managed identity → storage |
| RBAC: Key Vault Secrets User | `providers/azure/runtime` | Managed identity → Key Vault |

---

## Naming Convention

Pattern: `{type}-cna-platform-{env}-{region_short}`

| Resource | Dev example |
|---|---|
| Resource group | `rg-cna-platform-dev-eus` |
| VNet | `vnet-cna-platform-dev-eus` |
| Container Apps Env | `cae-cna-platform-dev-eus` |
| Container App (API) | `ca-cna-api-dev-eus` |
| Container App (Worker) | `ca-cna-worker-dev-eus` |
| Storage account | `stcnadeliveriesdeveus` (no hyphens, max 24 chars) |
| Key Vault | `kv-cna-platform-dev-eus` (max 24 chars) |
| App Insights | `appi-cna-platform-dev-eus` |
| Log Analytics | `law-cna-platform-dev-eus` |
| Front Door profile | `afd-cna-platform-dev-eus` |
| Terraform state RG | `rg-cna-tfstate-eus` |
| Terraform state SA | `stcnatfstateeus` |

---

## Workflow Sequence — Do Not Skip Steps

This is the sequence that works. The Spec Builder went in circles when the order
was violated (state drift, RBAC propagation failures, image pull errors).

```
Step 0: Bootstrap Terraform backend (one-time, manual)
  → az group create + az storage account create + az storage container create
  → Document resource names in GitHub Variables (TFSTATE_*)

Step 1: Create OIDC App Registration (one-time, manual)
  → az ad app create → az ad sp create → federated credential for main branch
  → Assign: Contributor at subscription scope (Terraform)
  → Assign: Storage Blob Data Contributor on tfstate storage account
  → Capture client-id → set CNA_AZURE_CLIENT_ID secret
  → Capture object-id → set CNA_AZURE_OIDC_PRINCIPAL_ID secret

Step 2: Build and push images (workflow: build-and-publish-images.yml)
  → Runs on push to main (apps/cna-api/**, apps/cna-worker/**)
  → Publishes to ghcr.io/saulpatinojr/cna-api and cna-worker
  → Tags: latest + sha-XXXXXXX
  → MUST run before deploy — Container Apps need a valid image reference

Step 3: Deploy Azure runtime (workflow: deploy-azure-runtime.yml)
  → Inputs: environment (dev|prod), api_image, worker_image, deploy_mode (release|rollback)
  → Jobs: policy-gates → plan → apply → verify → release-catalog
  → Terraform applies all modules in dependency order
  → After apply: directly queries Azure Monitor + App Insights for evidence
  → Threshold gates: health ≥ 95%, success rate ≥ 99%, cert expiry > 30 days
  → Front Door promotion: canary 10% → primary 90% with rollback support

Step 4: Set Key Vault secrets (post-deploy, manual — required before cna analyze)
  → az keyvault secret set --vault-name kv-cna-platform-dev-eus \
       --name cna-azure-openai-endpoint --value <endpoint>
  → az keyvault secret set ... --name cna-applicationinsights-connection-string \
       --value <connection_string>
  (Terraform outputs both values after apply)

Step 5: Run sync-env (optional — workflow: cd-publish.yml or manual)
  → Download .env artifact from Key Vault for local dev
```

---

## Why GHCR Instead of ACR

The Spec Builder uses ACR because it needs image scanning via Azure Defender
and the image is private to the Azure subscription. CNA uses GHCR because:

- `build-and-publish-images.yml` already publishes to GHCR using `GITHUB_TOKEN`
  (no secrets needed)
- GHCR images can be scoped to a repo and made private — same security posture
- Eliminates one Terraform resource (ACR) and the associated RBAC assignment
- Container Apps support GHCR pull via SystemAssigned identity with a `registry`
  block pointing to `ghcr.io` — no credential management needed

If ACR is needed in future (e.g., Azure Defender scanning, geo-replication),
add `providers/azure/registry` module and update `compute` module variables.

---

## OIDC Setup — Exact Steps

Based on what worked in Spec Builder (no service principal keys, ever):

```bash
# 1. Create app registration
az ad app create --display-name "cna-github-oidc"

# 2. Create service principal
az ad sp create --id <app-id>

# 3. Add federated credential for main branch
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "cna-main-branch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 4. Assign Contributor at subscription scope (Terraform needs this)
az role assignment create \
  --role Contributor \
  --assignee-object-id <sp-object-id> \
  --assignee-principal-type ServicePrincipal \
  --scope /subscriptions/<subscription-id>

# 5. Assign Storage Blob Data Contributor on tfstate storage account
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee-object-id <sp-object-id> \
  --assignee-principal-type ServicePrincipal \
  --scope /subscriptions/<sub>/resourceGroups/rg-cna-tfstate-eus/providers/Microsoft.Storage/storageAccounts/stcnatfstateeus

# 6. Set GitHub secrets
#   CNA_AZURE_CLIENT_ID      = <app-id>
#   CNA_AZURE_TENANT_ID      = <tenant-id>
#   CNA_AZURE_SUBSCRIPTION_ID = <subscription-id>
#   CNA_AZURE_OIDC_PRINCIPAL_ID = <sp-object-id>
```

---

## Terraform Backend Bootstrap

One-time manual setup (no workflow exists yet — add one if needed):

```bash
az group create --name rg-cna-tfstate-eus --location eastus

az storage account create \
  --name stcnatfstateeus \
  --resource-group rg-cna-tfstate-eus \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2

az storage container create \
  --name tfstate \
  --account-name stcnatfstateeus
```

Then set GitHub Variables:

| Variable | Value |
|---|---|
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate-eus` |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstateeus` |
| `TFSTATE_CONTAINER` | `tfstate` |

---

## Secrets Checklist — Before First Deploy

### GitHub Secrets (required)

- [ ] `CNA_AZURE_CLIENT_ID` — OIDC app registration client ID
- [ ] `CNA_AZURE_TENANT_ID` — Azure AD tenant GUID
- [ ] `CNA_AZURE_SUBSCRIPTION_ID` — Subscription ID
- [ ] `CNA_AZURE_OIDC_PRINCIPAL_ID` — OIDC SP object ID (for RBAC assignments)

### GitHub Secrets (required for AWS delivery)

- [ ] `CNA_AWS_ROLE_ARN` — ARN of `CNA-Publish` IAM role
- [ ] `CNA_PUBLISH_BUCKET` — S3 bucket for AWS delivery portal

### GitHub Secrets (optional)

- [ ] `FRONTDOOR_CERTIFICATE_PFX_PASSWORD` — Custom TLS cert password (if using BYO cert)

### GitHub Variables (required for `deploy-azure-runtime.yml`)

- [ ] `TFSTATE_RESOURCE_GROUP`
- [ ] `TFSTATE_STORAGE_ACCOUNT`
- [ ] `TFSTATE_CONTAINER`
- [ ] `APPLICATION_INSIGHTS_NAME`
- [ ] `KEY_VAULT_NAME`
- [ ] `FRONTDOOR_CERTIFICATE_NAME` (if using custom domain TLS)
- [ ] `FRONTDOOR_CERTIFICATE_PFX_PATH` (if using custom domain TLS)

### Key Vault Secrets (set post-deploy via CLI)

- [ ] `cna-azure-openai-endpoint` — from `terraform output azure_openai_endpoint`
- [ ] `cna-applicationinsights-connection-string` — from `terraform output app_insights_connection_string`

---

## Stale State / Cycle Prevention

The Spec Builder encountered several deployment cycles. Mitigations already in
`deploy-azure-runtime.yml` for CNA:

1. **Stale lock detection** — workflow reads state, extracts lock ID, force-unlocks.
2. **Import pass before apply** — existing resources imported by naming convention
   to prevent "already exists" drift errors.
3. **RBAC propagation wait** — 120s sleep after managed identity creation before
   Container Apps pull attempt.
4. **Image pull retry path** — if `ContainerAppOperationError` is detected, import
   pass runs again + RBAC wait + fresh plan.
5. **Concurrency group** — `cancel-in-progress: false` on deploy job prevents
   two deployments from racing on tfstate.

Do not add `--auto-approve` blindly. Always run plan first in a new environment.

---

## Differences from Spec Builder

| Topic | Spec Builder | CNA |
|---|---|---|
| Language/runtime | Next.js (Node 20) | Python 3.11/3.12 |
| Container count | 1 (web app) | 2 (api + worker) |
| Image registry | ACR (private) | GHCR (repo-scoped) |
| Database | PostgreSQL Flexible Server | None (blob + local disk) |
| CDN/Edge | App Gateway + Front Door | Front Door only |
| Primary client data store | SQL (Prisma) | Blob storage (engagements/) |
| Auth (app) | Entra ID / NextAuth | N/A (CLI tool, no web auth) |
| Terraform structure | `terraform/` flat | `infra/terraform/providers/azure/` modular |
| Workflow numbering | `01-` through `08-` | Named workflows (no numbering) |
| Key Vault secrets naming | `azure-ad-client-secret`, `database-url` | `cna-azure-openai-endpoint`, `cna-applicationinsights-connection-string` |

---

## Next Steps for Azure Infra (prioritized)

1. **Bootstrap Terraform backend** (manual, 5 min) — create RG + SA + container, set Variables.
2. **Create OIDC app registration** (manual, 10 min) — follow exact steps above, set Secrets.
3. **Verify Terraform modules validate** — `terraform init && terraform validate` in
   `infra/terraform/environments/azure/dev/` with backend config.
4. **Build first image** — push a commit to `main` touching `apps/cna-api/**` to trigger
   `build-and-publish-images.yml`. Confirm `ghcr.io/saulpatinojr/cna-api:latest` appears.
5. **Run first deploy** — `deploy-azure-runtime.yml`, env=dev, deploy_mode=release.
6. **Set Key Vault secrets** — post-deploy, set the two KV secrets from Terraform outputs.
7. **Smoke test** — `cna discover azure --engagement-id test-$(date +%Y%m%d)-0001 --tenant-id <TENANT_ID>`
   from a machine with `az login` and Reader at MG root.

---

*This document supersedes any informal notes on Azure infra sequencing.
Update it when deployment behavior changes.*
