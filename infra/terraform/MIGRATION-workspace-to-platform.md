# Migration runbook — move Log Analytics workspace from workload → platform state

> **Only needed for an ALREADY-DEPLOYED environment.** For a fresh/first
> deployment (no existing Terraform state, no existing workspace), skip this
> entire runbook — the platform root creates the workspace in the correct state
> from the start and there is nothing to migrate. As of the last check, no
> environment was deployed, so this is a no-op for the initial rollout. Keep
> this doc for any future environment that already has the workspace in
> workload state.

## Why

The Log Analytics workspace (`<name_prefix>-log`) used to be created by the
`compute` module, which lives in **workload** state. It has been moved to the
**platform** landing zone so that platform-owned resources (firewall, NSGs, VNet
flow logs) send diagnostics to a workspace in the same state that creates them —
removing the cross-state dependency.

The Terraform code change is done. **But the resource still physically exists in
workload state.** If you run `terraform apply` without migrating state first:

- **workload** plan will want to **destroy** `module.compute.azurerm_log_analytics_workspace.compute`
- **platform** plan will want to **create** `azurerm_log_analytics_workspace.platform`

That destroy/create **deletes all historical log data** and forces every
diagnostic setting to be torn down and recreated. To avoid that, migrate the
existing workspace between state files with `terraform state mv` (via pull/push,
since the two roots have separate backends).

Run this **once per environment** (dev, then prod) **before** the next apply.

---

## Preconditions

- Azure CLI authenticated with rights to the tfstate storage account.
- `terraform` 1.14.x on PATH.
- Both roots initialized against their real backends (the deploy pipeline does
  this; locally, `terraform init -backend-config=...` with the same keys the
  workflow uses — see `211-deploy-azure-split.yml`).
- **Take a state backup first** (copy the two blobs, or `terraform state pull >
  backup-<root>-<env>.tfstate` for each root).

## State addresses

| | Address |
|---|---|
| Source (workload state) | `module.compute.azurerm_log_analytics_workspace.compute` |
| Destination (platform state) | `azurerm_log_analytics_workspace.platform` |

The Azure resource ID is unchanged — only which state file tracks it changes:
```
/subscriptions/<SUB>/resourceGroups/rg-<name_prefix>/providers/Microsoft.OperationalInsights/workspaces/<name_prefix>-log
```

---

## Procedure (per environment)

Replace `<env>` with `dev` or `prod`. Backend keys mirror the deploy workflow:
platform = `<env>.terraform.tfstate`, workload = `<env>.workload.terraform.tfstate`.

### 1. Back up both states
```bash
cd infra/terraform/environments/azure/<env>/workload
terraform state pull > /tmp/backup-workload-<env>.tfstate
cd ../platform
terraform state pull > /tmp/backup-platform-<env>.tfstate
```

### 2. Remove the workspace from workload state (do NOT destroy)
```bash
cd infra/terraform/environments/azure/<env>/workload
terraform state rm 'module.compute.azurerm_log_analytics_workspace.compute'
```
`state rm` forgets the resource in Terraform without touching Azure — the
workspace keeps running and retains its data.

### 3. Import the existing workspace into platform state
```bash
cd ../platform
terraform import 'azurerm_log_analytics_workspace.platform' \
  "/subscriptions/<SUB>/resourceGroups/rg-<name_prefix>/providers/Microsoft.OperationalInsights/workspaces/<name_prefix>-log"
```
> `name_prefix` = `cna-<env>-scus`. Get `<SUB>` from `az account show --query id -o tsv`.

### 4. Verify both plans are clean
```bash
# platform: workspace should show NO changes (already exists, now tracked here).
# It WILL want to CREATE the new flow-logs storage account + observability
# diagnostic settings — that is expected and correct.
cd ../platform && terraform plan

# workload: should show NO destroy of the workspace. compute env now reads it
# via data source; observability is app-only.
cd ../workload && terraform plan
```

**Stop and investigate if the platform plan wants to _create_ the workspace or
the workload plan wants to _destroy_ it** — that means the import/rm didn't take.

### 5. Apply platform first, then workload
Platform must apply before workload so the workspace + outputs exist for the
workload's `data.azurerm_log_analytics_workspace.platform` lookup. This matches
the existing deploy order in `211-deploy-azure-split.yml`.

---

## Notes

- The dedicated flow-logs storage account (`<name_prefix>flowlog`) and the
  firewall/NSG/flow-log diagnostic settings are **new** resources created by
  platform — no migration needed, they just appear on first platform apply.
- Retention is set to 30 days in `platform/locals.tf` for both envs.
  **[REVIEW REQUIRED]** prod was 90 before the FinOps pass — confirm 30 meets
  any audit/compliance obligation before applying prod.
- If you would rather not do state surgery, the alternative is to accept the
  one-time workspace recreation (log-history loss) and just apply — not
  recommended for prod.
