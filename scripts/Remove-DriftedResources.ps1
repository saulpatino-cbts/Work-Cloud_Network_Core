<#
.SYNOPSIS
    Removes Azure resources that exist in the live environment but are NOT
    managed by Terraform (drifted / manually created resources).

.DESCRIPTION
    Three resources were identified as drift in the dev environment:
      1. aoaicnadevscus      — standalone Azure OpenAI (separate from Foundry)
      2. pe-cna-dev-scus-openai   — private endpoint for the above
      3. privatelink.openai.azure.com — private DNS zone for the above

    Run this script BEFORE or AFTER a full teardown/redeploy to ensure these
    do not block a clean Terraform apply.

.PARAMETER SubscriptionId
    Azure subscription ID. Defaults to the sub-cbtssandbox-conn-tst subscription.

.PARAMETER ResourceGroup
    Resource group containing the drifted resources. Defaults to the old
    naming-convention RG name; pass the new name if already renamed.

.PARAMETER DryRun
    If set, reports what would be deleted without actually deleting anything.

.EXAMPLE
    .\Remove-DriftedResources.ps1 -DryRun

.EXAMPLE
    .\Remove-DriftedResources.ps1 -ResourceGroup "cbts-cna-dev-scus-rg"
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $SubscriptionId = "ffa5d839-0f87-4cde-ab8c-4e59b19f346b",
    [string] $ResourceGroup  = "rg-cna-dev-scus",
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Msg) { Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok([string]$Msg)   { Write-Host "    [OK] $Msg" -ForegroundColor Green }
function Write-Skip([string]$Msg) { Write-Host "    [--] $Msg" -ForegroundColor Gray }
function Write-Warn([string]$Msg) { Write-Host "    [!] $Msg"  -ForegroundColor Yellow }

# ── Login check ───────────────────────────────────────────────────────────────
Write-Step "Verifying Azure CLI session"
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Error "Not logged in. Run 'az login' first."
}
Write-Ok "Logged in as: $($account.user.name)"

az account set --subscription $SubscriptionId
Write-Ok "Active subscription: $SubscriptionId"

# ── Helper: check resource exists ─────────────────────────────────────────────
function Test-CognitiveAccount([string]$Name, [string]$Rg) {
    $result = az cognitiveservices account show --name $Name --resource-group $Rg 2>$null
    return ($null -ne $result)
}

function Test-PrivateEndpoint([string]$Name, [string]$Rg) {
    $result = az network private-endpoint show --name $Name --resource-group $Rg 2>$null
    return ($null -ne $result)
}

function Test-PrivateDnsZone([string]$Name, [string]$Rg) {
    $result = az network private-dns zone show --name $Name --resource-group $Rg 2>$null
    return ($null -ne $result)
}

# ── 1. Standalone Azure OpenAI ────────────────────────────────────────────────
Write-Step "Checking standalone Azure OpenAI account (aoaicnadevscus)"
$oaiNames = @("aoaicnadevscus", "aoaicnaprodscus")
foreach ($oaiName in $oaiNames) {
    if (Test-CognitiveAccount -Name $oaiName -Rg $ResourceGroup) {
        if ($DryRun) {
            Write-Warn "DRY RUN — would delete Cognitive Services account: $oaiName"
        } else {
            Write-Host "    Deleting: $oaiName ..." -ForegroundColor Yellow
            az cognitiveservices account delete `
                --name $oaiName `
                --resource-group $ResourceGroup `
                --yes
            Write-Ok "Deleted: $oaiName"
        }
    } else {
        Write-Skip "$oaiName not found in $ResourceGroup — skipping"
    }
}

# ── 2. OpenAI private endpoint ────────────────────────────────────────────────
Write-Step "Checking OpenAI private endpoint"
$pepNames = @("pe-cna-dev-scus-openai", "pe-cna-prod-scus-openai", "cbts-cna-dev-scus-pep-oai", "cbts-cna-prod-scus-pep-oai")
foreach ($pepName in $pepNames) {
    if (Test-PrivateEndpoint -Name $pepName -Rg $ResourceGroup) {
        if ($DryRun) {
            Write-Warn "DRY RUN — would delete private endpoint: $pepName"
        } else {
            Write-Host "    Deleting: $pepName ..." -ForegroundColor Yellow
            az network private-endpoint delete `
                --name $pepName `
                --resource-group $ResourceGroup
            Write-Ok "Deleted: $pepName"
        }
    } else {
        Write-Skip "$pepName not found — skipping"
    }
}

# ── 3. OpenAI private DNS zone ────────────────────────────────────────────────
Write-Step "Checking privatelink.openai.azure.com DNS zone"
if (Test-PrivateDnsZone -Name "privatelink.openai.azure.com" -Rg $ResourceGroup) {
    if ($DryRun) {
        Write-Warn "DRY RUN — would delete DNS zone: privatelink.openai.azure.com"
    } else {
        Write-Host "    Deleting DNS zone: privatelink.openai.azure.com ..." -ForegroundColor Yellow
        az network private-dns zone delete `
            --name "privatelink.openai.azure.com" `
            --resource-group $ResourceGroup `
            --yes
        Write-Ok "Deleted DNS zone"
    }
} else {
    Write-Skip "privatelink.openai.azure.com not found in $ResourceGroup — skipping"
}

# ── 4. Auto-generated Foundry account (adms-* naming) ────────────────────────
Write-Step "Checking auto-generated Foundry accounts (adms-* prefix)"
$allCognitive = az cognitiveservices account list --resource-group $ResourceGroup 2>$null | ConvertFrom-Json
if ($allCognitive) {
    $admsAccounts = $allCognitive | Where-Object { $_.name -like "adms-*" }
    foreach ($acct in $admsAccounts) {
        if ($DryRun) {
            Write-Warn "DRY RUN — would delete auto-generated Foundry account: $($acct.name)"
        } else {
            Write-Host "    Deleting: $($acct.name) ..." -ForegroundColor Yellow
            az cognitiveservices account delete `
                --name $acct.name `
                --resource-group $ResourceGroup `
                --yes
            Write-Ok "Deleted: $($acct.name)"
        }
    }
    if (-not $admsAccounts) {
        Write-Skip "No adms-* accounts found"
    }
}

Write-Step "Done"
if ($DryRun) {
    Write-Host "`nDry run complete — nothing was deleted. Re-run without -DryRun to apply." -ForegroundColor Cyan
} else {
    Write-Host "`nDrift cleanup complete. Safe to run 031-deploy-azure with a clean Terraform apply." -ForegroundColor Green
}
