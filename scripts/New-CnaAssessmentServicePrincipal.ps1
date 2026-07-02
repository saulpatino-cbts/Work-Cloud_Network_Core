<#
.SYNOPSIS
Creates the read-only Azure service principal the CNA app's "Add Cloud
Connection" form asks for, and emits everything the form needs.

.DESCRIPTION
The deploy identities from Initialize-CnaGitHubSecrets.ps1 are deliberately
unusable here: the Main/Dev/Prod SPs are GitHub-OIDC-only (they hold no
client secret at all) and carry deploy-level rights, and the "CNA Assessment
Tool" app registration is the NextAuth sign-in identity. The assessment
connection instead needs its own least-privilege SP: Reader on each target
subscription, authenticating with a client secret the app stores encrypted
at rest.

Idempotent by display name: re-running reuses the existing app/SP and role
assignments and mints a fresh client secret (shown once — Azure never
returns it again). Also writes the subscription CSV in the exact format the
form's "Import CSV" expects (subscription_name,subscription_id,tenant_id).

.PARAMETER DisplayName
Entra display name for the assessment app registration.

.PARAMETER SubscriptionIds
Subscription IDs the assessment SP should be able to read. When omitted,
defaults to EVERY enabled subscription in the tenant you are logged into —
the assessment covers the whole tenant unless you narrow it explicitly.

.PARAMETER SecretYears
Client secret lifetime in years.

.PARAMETER SkipSecret
Skip minting a new client secret. Use on re-runs that only extend role
assignments to more subscriptions — the secret already saved in the app's
connection keeps working (credential resets here always --append).

.PARAMETER CsvPath
Where to write the subscription import CSV. Defaults to
scripts/.reports/assessment/<timestamp>-subscriptions.csv.

.EXAMPLE
# Tenant-wide scanner (all enabled subscriptions in the current tenant):
./scripts/New-CnaAssessmentServicePrincipal.ps1

.EXAMPLE
# Narrow to specific subscriptions:
./scripts/New-CnaAssessmentServicePrincipal.ps1 -SubscriptionIds @("<sub-id-1>", "<sub-id-2>")

.EXAMPLE
# Extend an existing scanner to newly added subscriptions without rotating its secret:
./scripts/New-CnaAssessmentServicePrincipal.ps1 -SkipSecret
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$DisplayName = "CNA Assessment Scanner",

    [string[]]$SubscriptionIds = @(),

    [ValidateRange(1, 2)]
    [int]$SecretYears = 1,

    [switch]$SkipSecret,

    [string]$CsvPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step { param([string]$Message) Write-Host ""; Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok { param([string]$Message) Write-Host "    [OK] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "    [WARN] $Message" -ForegroundColor Yellow }

Write-Step "Checking Azure CLI login"
$account = az account show -o json 2>$null | ConvertFrom-Json
if (-not $account) {
    throw "Not logged in. Run 'az login' first."
}
$tenantId = [string]$account.tenantId
Write-Ok "Logged in as $($account.user.name) (tenant $tenantId)"

Write-Step "Resolving target subscriptions"
$subscriptions = @()
if ($SubscriptionIds.Count -eq 0) {
    # Default: the whole tenant. The scanner is expected to see every enabled
    # subscription the assessment could target; narrowing is the explicit
    # opt-in (-SubscriptionIds), not the default.
    $tenantSubs = az account list --query "[?tenantId=='$tenantId' && state=='Enabled'].{id:id, name:name, tenantId:tenantId}" -o json | ConvertFrom-Json
    if (-not $tenantSubs -or @($tenantSubs).Count -eq 0) {
        throw "No enabled subscriptions visible in tenant $tenantId. Run 'az login' with an account that can see the target subscriptions."
    }
    foreach ($sub in @($tenantSubs)) {
        $subscriptions += [pscustomobject]@{ Id = [string]$sub.id; Name = [string]$sub.name; TenantId = [string]$sub.tenantId }
        Write-Ok "$($sub.name) ($($sub.id))"
    }
    Write-Ok "Tenant-wide: $(@($subscriptions).Count) enabled subscription(s) in $tenantId"
} else {
    foreach ($subId in $SubscriptionIds) {
        $sub = az account show --subscription $subId -o json 2>$null | ConvertFrom-Json
        if (-not $sub) {
            throw "Subscription '$subId' is not visible to this login. Check the ID and your access."
        }
        if ([string]$sub.tenantId -ne $tenantId) {
            Write-Warn "Subscription $($sub.name) lives in tenant $($sub.tenantId), not $tenantId. The app connects with ONE tenant per connection — add it as a separate connection."
        }
        $subscriptions += [pscustomobject]@{ Id = [string]$sub.id; Name = [string]$sub.name; TenantId = [string]$sub.tenantId }
        Write-Ok "$($sub.name) ($($sub.id))"
    }
}

Write-Step "Ensuring app registration + service principal: $DisplayName"
$appId = (az ad app list --display-name $DisplayName --query "[0].appId" -o tsv 2>$null)
if (-not [string]::IsNullOrWhiteSpace($appId)) {
    $appId = $appId.Trim()
    Write-Ok "Using existing app registration ($appId)"
} else {
    if ($PSCmdlet.ShouldProcess($DisplayName, "create app registration")) {
        $appId = (az ad app create --display-name $DisplayName --query appId -o tsv).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($appId)) { throw "Failed to create app registration." }
    }
    Write-Ok "Created app registration ($appId)"
}

$spId = (az ad sp list --filter "appId eq '$appId'" --query "[0].id" -o tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($spId)) {
    if ($PSCmdlet.ShouldProcess($appId, "create service principal")) {
        az ad sp create --id $appId --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to create service principal." }
        Start-Sleep -Seconds 10
    }
    Write-Ok "Created service principal"
} else {
    Write-Ok "Service principal exists"
}

Write-Step "Assigning Reader on target subscriptions"
foreach ($sub in $subscriptions) {
    $scope = "/subscriptions/$($sub.Id)"
    $existing = az role assignment list --assignee $appId --role Reader --scope $scope --query "[0].id" -o tsv 2>$null
    if (-not [string]::IsNullOrWhiteSpace($existing)) {
        Write-Ok "Reader already assigned on $($sub.Name)"
        continue
    }
    if ($PSCmdlet.ShouldProcess($scope, "assign Reader to $DisplayName")) {
        az role assignment create --role Reader --assignee $appId --scope $scope --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to assign Reader on $($sub.Name)." }
    }
    Write-Ok "Assigned Reader on $($sub.Name)"
}

$secret = $null
if ($SkipSecret) {
    Write-Step "Skipping client secret creation (-SkipSecret)"
    Write-Ok "The secret already saved in the app's cloud connection keeps working."
} else {
    Write-Step "Creating client secret ($SecretYears year(s))"
    if ($PSCmdlet.ShouldProcess($appId, "reset client credential")) {
        $secret = (az ad app credential reset --id $appId --append --display-name "cna-assessment-$(Get-Date -Format yyyyMMddHHmmss)" --years $SecretYears --query password -o tsv 2>$null)
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($secret)) { throw "Failed to create client secret." }
        $secret = $secret.Trim()
    }
}

if ([string]::IsNullOrWhiteSpace($CsvPath)) {
    $CsvPath = Join-Path "scripts/.reports/assessment" "$((Get-Date).ToString('yyyyMMdd-HHmmss'))-subscriptions.csv"
}
$csvDir = Split-Path -Parent $CsvPath
if (-not [string]::IsNullOrWhiteSpace($csvDir)) {
    New-Item -ItemType Directory -Path $csvDir -Force | Out-Null
}
# Header must match the app's credential-form parser exactly:
# subscription_name,subscription_id,tenant_id (tenant auto-fills the form).
$lines = @("subscription_name,subscription_id,tenant_id")
foreach ($sub in $subscriptions) {
    $lines += "$($sub.Name),$($sub.Id),$($sub.TenantId)"
}
Set-Content -Path $CsvPath -Value ($lines -join "`n") -Encoding UTF8
Write-Ok "Wrote subscription import CSV: $CsvPath"

Write-Step "Values for the Add Cloud Connection form"
Write-Host ""
Write-Host "  Tenant ID        : $tenantId" -ForegroundColor White
Write-Host "  SP Client ID     : $appId" -ForegroundColor White
if ($null -ne $secret) {
    Write-Host "  SP Client Secret : $secret" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  The secret is shown ONCE and is not saved anywhere by this script." -ForegroundColor Yellow
    Write-Host "  Newly minted secrets can take a minute to propagate in Entra before 'Test connection' passes."
} else {
    Write-Host "  SP Client Secret : (unchanged — -SkipSecret)" -ForegroundColor White
}
Write-Host "  Subscriptions: use 'Import CSV' with the file above, or add rows manually."
