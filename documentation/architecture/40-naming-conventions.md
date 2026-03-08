# CNA Platform — Naming Conventions Reference

All names follow **Azure Cloud Adoption Framework (CAF)** abbreviations with the pattern:

```
{abbreviation}-{project}-{environment}-{region}
```

The `name_prefix` is computed in each environment's `locals.tf`:

```hcl
name_prefix = "${var.project_name}-${var.environment}-${var.region_short}"
# dev  → cna-dev-scus
# prod → cna-prod-scus
```

---

## Azure Region Short Codes

| Region | `location` value | `region_short` |
|---|---|---|
| South Central US | `southcentralus` | `scus` ✅ (this project) |
| East US | `eastus` | `eus` |
| East US 2 | `eastus2` | `eus2` |
| West US 2 | `westus2` | `wus2` |
| Central US | `centralus` | `cus` |
| North Central US | `northcentralus` | `ncus` |
| West Europe | `westeurope` | `weu` |
| North Europe | `northeurope` | `neu` |
| UK South | `uksouth` | `uks` |

---

## Azure Resources

| Resource Type | Pattern | Dev Example | Prod Example |
|---|---|---|---|
| Resource Group | `rg-{prefix}` | `rg-cna-dev-scus` | `rg-cna-prod-scus` |
| Container Apps Environment | `cae-{prefix}-platform` | `cae-cna-dev-scus-platform` | `cae-cna-prod-scus-platform` |
| Container App | `ca-{prefix}-{service}` | `ca-cna-dev-scus-api` | `ca-cna-prod-scus-api` |
| Key Vault | `kv-{prefix}` (max 24) | `kv-cna-dev-scus` | `kv-cna-prod-scus` |
| Managed Identity | `id-{prefix}-platform` | `id-cna-dev-scus-platform` | `id-cna-prod-scus-platform` |
| Storage Account | `st{prefix_no_hyphens}` (max 24) | `stcnadevscusplatform` | `stcnaprodscusplatform` |
| PostgreSQL Flexible Server | `psqlf-{prefix}-platform` | `psqlf-cna-dev-scus-platform` | `psqlf-cna-prod-scus-platform` |
| Application Insights | `appi-{prefix}-platform` | `appi-cna-dev-scus-platform` | `appi-cna-prod-scus-platform` |
| Azure OpenAI | `aoai{prefix_no_hyphens}` (max 24) | `aoaicnadevscus` | `aoaicnaprodscus` |
| Network Security Group | `nsg-{prefix}-platform` | `nsg-cna-dev-scus-platform` | `nsg-cna-prod-scus-platform` |
| Virtual Network | `vnet-{prefix}-platform` | `vnet-cna-dev-scus-platform` | `vnet-cna-prod-scus-platform` |
| Subnet | `snet-{prefix}-{purpose}` | `snet-cna-dev-scus-apps` | `snet-cna-prod-scus-apps` |
| Front Door Profile | `afd-{prefix}-platform` | `afd-cna-dev-scus-platform` | `afd-cna-prod-scus-platform` |
| Front Door Origin | `origin-{prefix}-web` | `origin-cna-dev-scus-web` | `origin-cna-prod-scus-web` |
| Front Door Route | `route-{prefix}-web` | `route-cna-dev-scus-web` | `route-cna-prod-scus-web` |
| WAF Policy | `afdwaf{prefix_no_hyphens}` | `afdwafcnadevscus` | `afdwafcnaprodscus` |
| CDN Profile | `cdn-{prefix}-platform` | `cdn-cna-dev-scus-platform` | `cdn-cna-prod-scus-platform` |
| Terraform State RG | `rg-{project}-tfstate` | `rg-cna-tfstate` | ← shared, no env/region |
| Terraform State SA | `st{project}tfstate` (max 24) | `stcnatfstate` | ← shared, no env/region |

> **Resource Group strategy:**
> - **Workload RGs** (`rg-cna-dev-scus`, `rg-cna-prod-scus`) — one per environment, created and
>   owned by Terraform. All platform resources live here.
> - **Terraform State RG** (`rg-cna-tfstate`) — dedicated to state only, created by workflow 01,
>   never touched by Terraform. Isolating state means a `terraform destroy` of a workload RG
>   cannot affect the state backend.

> **Character restriction rules:**
> - Storage Account: no hyphens, lowercase, max 24 → strip `-` with `replace()`
> - Azure OpenAI: no hyphens, lowercase, max 24 → strip `-` with `replace()`
> - WAF Policy: alphanumeric only (Azure hard requirement) → strip `-` with `replace()`
> - Key Vault: hyphens allowed, max 24 → `substr()` only

### Key Vault Secret Names

```
cna-azure-openai-endpoint
cna-applicationinsights-connection-string
cna-nextauth-secret
cna-postgres-admin-password
cna-entra-client-secret
```

### Azure Tags (all resources)

```hcl
tags = {
  project     = "cna"
  environment = "dev" | "prod"
  region      = "scus"
  managed_by  = "terraform"
  platform    = "cna"
}
```

---

## AWS Resources

| Resource Type | Pattern | Dev Example |
|---|---|---|
| VPC | `vpc-{prefix}` | `vpc-cna-dev-scus` |
| Subnet | `snet-{prefix}-{az}-{tier}` | `snet-cna-dev-scus-1a-private` |
| Security Group | `sg-{prefix}-{purpose}` | `sg-cna-dev-scus-api` |
| IAM Role | `role-{prefix}-{service}` | `role-cna-dev-scus-lambda` |
| IAM Policy | `policy-{prefix}-{purpose}` | `policy-cna-dev-scus-s3-read` |
| S3 Bucket | `s3-{prefix}-{purpose}` | `s3-cna-dev-scus-artifacts` |
| Lambda | `fn-{prefix}-{function}` | `fn-cna-dev-scus-discovery` |
| RDS Instance | `rds-{prefix}-{engine}` | `rds-cna-dev-scus-postgres` |

---

## Container Images (GHCR)

```
ghcr.io/saulpatinojr/cna-{service}:{git-sha}   ← immutable, used by Terraform
ghcr.io/saulpatinojr/cna-{service}:latest       ← floating, local dev only
ghcr.io/saulpatinojr/cna-{service}:v{semver}    ← set by workflow 09 on tag
```

Services: `api`, `worker`, `web`

---

## Repository & Code Conventions

| Layer | Convention | Example |
|---|---|---|
| GitHub Actions workflows | `NN-{slug}.yml` | `03-deploy-azure-dev.yml` |
| Architecture docs | `NN-{slug}.md` (sequential) | `40-naming-conventions.md` |
| Blog posts | `YYYY-MM-DD-{slug}.md` | `2026-03-08-github-actions-azure-oidc.md` |
| Gists | `NN-{slug}.md` (01-12) | `01-managed-identity-setup.md` |
| Python files/functions | `snake_case` | `discovery_engine.py` |
| Python classes | `PascalCase` | `class NetworkTopology` |
| TypeScript files | `kebab-case` | `auth-provider.ts` |
| TypeScript functions/vars | `camelCase` | `const sessionUser` |
| React components | `PascalCase` | `DashboardPage` |
| Terraform files | fixed names | `main.tf`, `variables.tf`, `outputs.tf`, `locals.tf` |
| Terraform resources | `snake_case` | `azurerm_key_vault.platform` |

---

## Anti-Patterns

| Wrong | Problem | Correct |
|---|---|---|
| `rg-cna-dev` | Missing region | `rg-cna-dev-scus` |
| `myKeyVault` | No abbreviation, no project/env/region | `kv-cna-dev-scus` |
| `storage-account-prod` | Hyphens not allowed in SA names | `stcnaprodscus` |
| `afd-waf-cna-dev-scus` | Hyphens not allowed in WAF names | `afdwafcnadevscus` |
| `CNA-DEV-API` | Uppercase not allowed in most Azure names | `ca-cna-dev-scus-api` |
| `dev-rg` | Env before project, missing abbreviation | `rg-cna-dev-scus` |
