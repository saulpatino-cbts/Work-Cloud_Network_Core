# CNA Azure Cleanup Inventory

This inventory separates two cleanup cases:

- `StaleAi`: remove only the old Azure OpenAI and failed portal-created Foundry artifacts.
- `Environment`: remove the full CNA environment resource groups, excluding the new Foundry RG by default.

Current desired Foundry resources:

| Environment | Resource group | Foundry account | Foundry project | Region |
| --- | --- | --- | --- | --- |
| dev | `rg-cna-ai-dev-eus2` | `fdry-cna-dev-eus2` | `proj-cna-dev-eus2` | `eastus2` |
| prod | `rg-cna-ai-prod-eus2` | `fdry-cna-prod-eus2` | `proj-cna-prod-eus2` | `eastus2` |

## Dev Resource Groups

| Resource group | Cleanup scope | Notes |
| --- | --- | --- |
| `rg-cna-dev-scus` | `Environment` | Main CNA workload RG: Container Apps, Front Door, VNet, Key Vault, Postgres, storage, App Insights, stale OpenAI, failed portal Foundry. |
| `ai_appi-cna-dev-scus-platform_b55a671e-e616-4d50-9990-baddbcd27bba_managed` | `Environment` | App Insights managed RG. |
| `ME_cae-cna-dev-scus-platform_rg-cna-dev-scus_southcentralus` | `Environment` | Container Apps managed environment RG. |
| `rg-cna-ai-dev-eus2` | `AllCna` or `Environment -IncludeFoundry` | Desired Foundry RG. Do not delete while Claude approval/configuration is in progress. |
| `rg-cna-tfstate` | Only with `-IncludeTfState` | Shared Terraform backend. Do not delete unless intentionally destroying all Terraform state. |

## Dev Stale AI Resources

These are safe cleanup candidates after the Foundry refactor:

| Resource type | Name | Resource group | Notes |
| --- | --- | --- | --- |
| Cognitive Services account | `aoaicnadevscus` | `rg-cna-dev-scus` | Old `kind=OpenAI` Azure OpenAI account. |
| Cognitive Services account | `adms-mnvji9i5-eastus2` | `rg-cna-dev-scus` | Portal-created Foundry attempt from the failed wizard flow. |
| Private endpoint | `pe-cna-dev-scus-openai` | `rg-cna-dev-scus` | Old OpenAI private endpoint. |
| Network interface | `pe-cna-dev-scus-openai.nic.*` | `rg-cna-dev-scus` | Child NIC for the OpenAI private endpoint. |
| Private DNS zone | `privatelink.openai.azure.com` | `rg-cna-dev-scus` | Old OpenAI private DNS zone. |
| Private DNS link | `pdns-link-cna-dev-scus-openai` | `rg-cna-dev-scus` | Child link under the OpenAI private DNS zone. |
| Key Vault secret | `cna-azure-openai-endpoint` | `kv-cna-dev-scus-platform` | Old endpoint secret. |
| Role assignments | `Cognitive Services OpenAI User` | Scope `aoaicnadevscus` | Old Container App identity assignments. |

## Script Usage

List full environment cleanup surface, excluding Foundry and tfstate:

```powershell
.\scripts\cleanup-stale-ai-resources.ps1 -Environment dev -Scope Environment
```

This scope is intentionally limited to CNA-owned environment groups:

- `rg-cna-<env>-scus`
- `ai_appi-cna-<env>-scus-platform_*_managed`
- `ME_cae-cna-<env>-scus-platform_rg-cna-<env>-scus_*`

It must not include landing-zone/shared groups such as `cbtssandbox-*`, `NetworkWatcherRG`, or `rg-cna-tfstate`.

List only stale AI artifacts:

```powershell
.\scripts\cleanup-stale-ai-resources.ps1 -Environment dev -Scope StaleAi
```

Delete only stale AI artifacts:

```powershell
.\scripts\cleanup-stale-ai-resources.ps1 -Environment dev -Scope StaleAi -Delete
```

Delete the full dev environment but keep the desired Foundry RG:

```powershell
.\scripts\cleanup-stale-ai-resources.ps1 -Environment dev -Scope Environment -Delete
```

Include the desired Foundry RG in an environment delete:

```powershell
.\scripts\cleanup-stale-ai-resources.ps1 -Environment dev -Scope Environment -IncludeFoundry -Delete
```

Include Terraform state only when intentionally destroying the deployment backend:

```powershell
.\scripts\cleanup-stale-ai-resources.ps1 -Environment dev -Scope AllCna -IncludeTfState -Delete
```
