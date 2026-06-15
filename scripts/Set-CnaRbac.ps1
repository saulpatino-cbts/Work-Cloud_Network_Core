<#
.SYNOPSIS
  Step-zero RBAC preflight for CNA deployments.

.DESCRIPTION
  Ensures every Container App managed identity has the role assignments it
  needs before the 031 deploy workflow runs. Safe to re-run — existing
  assignments are detected and skipped. Run this once after a fresh infra
  bootstrap (000 workflow) or whenever a new role requirement is added.

  Required caller permissions:
    - User Access Administrator (or Owner) on the subscription or
      on each resource scope individually.

.PARAMETER Environment
  Target environment: dev | prod  (default: dev)

.PARAMETER SubscriptionId
  Azure subscription ID (default: ffa5d839-0f87-4cde-ab8c-4e59b19f346b)

.PARAMETER Location
  Azure region short name used in resource naming (default: scus)

.EXAMPLE
  # Dev (default)
  ./scripts/Set-CnaRbac.ps1

  # Prod
  ./scripts/Set-CnaRbac.ps1 -Environment prod
#>
[CmdletBinding()]
param(
  [ValidateSet("dev", "prod")]
  [string]$Environment = "dev",

  [string]$SubscriptionId = "ffa5d839-0f87-4cde-ab8c-4e59b19f346b",

  [string]$Location = "scus"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Derived names (must match Terraform locals) ────────────────────────────────
$prefix        = "cna-$Environment-$Location"        # e.g. cna-dev-scus
$rg            = "rg-$prefix"                         # rg-cna-dev-scus
$openaiName    = ("aoai-$prefix" -replace "-","").ToLower().Substring(0, [Math]::Min(24, ("aoai-$prefix" -replace "-","").Length))
$storageName   = ("st${prefix}platform" -replace "-","").ToLower().Substring(0, [Math]::Min(24, ("st${prefix}platform" -replace "-","").Length))

$appNames = @{
  web    = "ca-$prefix-web"
  api    = "ca-$prefix-api"
  worker = "ca-$prefix-worker"
}

Write-Host ""
Write-Host "=== CNA RBAC Preflight ===" -ForegroundColor Cyan
Write-Host "Environment : $Environment"
Write-Host "Subscription: $SubscriptionId"
Write-Host "Resource Grp: $rg"
Write-Host "OpenAI Acct : $openaiName"
Write-Host "Storage Acct: $storageName"
Write-Host ""

# ── Set subscription context ───────────────────────────────────────────────────
Write-Host "Setting subscription context..." -ForegroundColor Gray
az account set --subscription $SubscriptionId | Out-Null

# ── Resolve resource IDs ───────────────────────────────────────────────────────
Write-Host "Resolving resource IDs..." -ForegroundColor Gray

$openaiId = az cognitiveservices account show `
  --name $openaiName `
  --resource-group $rg `
  --query id -o tsv 2>$null
if (-not $openaiId) { throw "Azure OpenAI account '$openaiName' not found in '$rg'. Has the 031 deploy run at least once?" }

$storageId = az storage account show `
  --name $storageName `
  --resource-group $rg `
  --query id -o tsv 2>$null
if (-not $storageId) { throw "Storage account '$storageName' not found in '$rg'." }

Write-Host "  OpenAI  : $openaiId" -ForegroundColor DarkGray
Write-Host "  Storage : $storageId" -ForegroundColor DarkGray
Write-Host ""

# ── Resolve Container App principal IDs ───────────────────────────────────────
Write-Host "Resolving Container App managed identity principal IDs..." -ForegroundColor Gray
$principals = @{}
foreach ($role in $appNames.Keys) {
  $name = $appNames[$role]
  $pid = az containerapp show `
    --name $name `
    --resource-group $rg `
    --query "identity.principalId" -o tsv 2>$null
  if (-not $pid) { throw "Container App '$name' not found or has no system-assigned identity. Has the 031 deploy run?" }
  $principals[$role] = $pid
  Write-Host "  $role ($name): $pid" -ForegroundColor DarkGray
}
Write-Host ""

# ── Role assignment matrix ─────────────────────────────────────────────────────
# Each entry: [principalId, roleName, scope, description]
$assignments = @(
  # Storage Blob Data Contributor
  @($principals.web,    "Storage Blob Data Contributor",      $storageId, "web → Storage (deliverable uploads)"),
  @($principals.api,    "Storage Blob Data Contributor",      $storageId, "api → Storage (artifact read/write)"),
  @($principals.worker, "Storage Blob Data Contributor",      $storageId, "worker → Storage (artifact processing)"),

  # Cognitive Services User
  @($principals.web,    "Cognitive Services User",     $openaiId,  "web → AI service (AI analysis + deliverable generation)"),
  @($principals.api,    "Cognitive Services User",     $openaiId,  "api → AI service (discovery AI enrichment)"),
  @($principals.worker, "Cognitive Services User",     $openaiId,  "worker → AI service (background AI tasks)")
)

# ── Apply assignments (idempotent) ─────────────────────────────────────────────
$created = 0
$skipped = 0
$failed  = 0

foreach ($a in $assignments) {
  $principalId, $roleName, $scope, $desc = $a

  # Check if assignment already exists
  $existing = az role assignment list `
    --assignee $principalId `
    --role $roleName `
    --scope $scope `
    --query "[0].id" -o tsv 2>$null

  if ($existing) {
    Write-Host "  [SKIP] $desc" -ForegroundColor DarkGray
    $skipped++
    continue
  }

  Write-Host "  [CREATE] $desc" -ForegroundColor Yellow
  try {
    az role assignment create `
      --assignee $principalId `
      --role $roleName `
      --scope $scope `
      --output none
    Write-Host "           -> OK" -ForegroundColor Green
    $created++
  } catch {
    Write-Host "           -> FAILED: $_" -ForegroundColor Red
    $failed++
  }
}

# ── Summary ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "  Created : $created"
Write-Host "  Skipped : $skipped (already exist)"
Write-Host "  Failed  : $failed"
Write-Host ""

if ($failed -gt 0) {
  Write-Error "$failed assignment(s) failed. Check output above. Caller needs User Access Administrator on the subscription."
}
