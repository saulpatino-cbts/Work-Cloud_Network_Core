[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Repo,

    [string]$Branch = "main",

    [ValidateSet("dev", "prod")]
    [string]$Environment = "dev",

    [string]$SubscriptionId,

    [string]$AppDisplayName,

    [switch]$SkipAzureSetup,

    [string]$BootstrapLocation = "southcentralus",

    [string]$BootstrapRegionShort = "scus",

    [string]$ReportDirectory = ".reports/bootstrap",

    [switch]$SkipBootstrapDispatch,

    [switch]$ForceInteractive
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    [!] $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "    [INFO] $Message" -ForegroundColor DarkCyan
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name CLI not found. Install it and rerun this script."
    }
}

function ConvertFrom-SecureStringToPlainText {
    param([System.Security.SecureString]$Value)
    if (-not $Value -or $Value.Length -eq 0) { return "" }
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Initialize-AzLogin {
    [CmdletBinding()]
    param()

    Write-Step "Checking Azure CLI session"
    $account = Invoke-AzJson -Arguments @("account", "show")
    if ($account) {
        Write-Ok "Azure CLI is already signed in as $($account.name) ($($account.id))"
        return $account
    }

    Write-Warn "Azure CLI is not currently signed in. Starting interactive login..."
    & az login --use-device-code
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI login failed. Re-run the script after signing in."
    }

    $account = Invoke-AzJson -Arguments @("account", "show")
    if (-not $account) {
        throw "Azure CLI login completed but no account context is available yet."
    }

    return $account
}

function Select-AzSubscription {
    [CmdletBinding()]
    param([object]$CurrentAccount)

    $accounts = Invoke-AzJson -Arguments @("account", "list")
    if (-not $accounts -or $accounts.Count -eq 0) {
        throw "No Azure subscriptions are available. Sign in with az login first."
    }

    if ($SubscriptionId) {
        $selected = $accounts | Where-Object { $_.id -eq $SubscriptionId -or $_.name -eq $SubscriptionId } | Select-Object -First 1
        if ($selected) {
            Write-Ok "Using requested subscription: $($selected.name) ($($selected.id))"
            return $selected
        }
        throw "Requested subscription '$SubscriptionId' was not found in the current Azure account context."
    }

    if ($accounts.Count -eq 1) {
        $selected = $accounts[0]
        Write-Ok "Using the only available subscription: $($selected.name) ($($selected.id))"
        return $selected
    }

    $selected = $null
    if ($CurrentAccount -and $CurrentAccount.id) {
        $selected = $accounts | Where-Object { $_.id -eq $CurrentAccount.id } | Select-Object -First 1
    }
    if (-not $selected) {
        $selected = $accounts | Where-Object { $_.isDefault -eq $true } | Select-Object -First 1
    }
    if (-not $selected) {
        $selected = $accounts[0]
    }

    Write-Host "Available Azure subscriptions:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $accounts.Count; $i++) {
        $a = $accounts[$i]
        $marker = if ($selected -and $a.id -eq $selected.id) { " [default]" } else { "" }
        Write-Host "  [$i] $($a.name) ($($a.id))  tenant=$($a.tenantId)$marker"
    }

    while ($true) {
        $defaultLabel = if ($selected) { "$($selected.name) / $($selected.id)" } else { "none" }
        $choice = Read-Host "Select a subscription by number, or type the subscription ID/name (default: $defaultLabel)"
        if ([string]::IsNullOrWhiteSpace($choice) -and $selected) {
            return $selected
        }

        $selected = $accounts | Where-Object { $_.id -eq $choice -or $_.name -eq $choice }
        if ($selected) {
            return $selected[0]
        }

        if ($choice -match '^\d+$' -and [int]$choice -ge 0 -and [int]$choice -lt $accounts.Count) {
            return $accounts[[int]$choice]
        }

        Write-Warn "That selection was not found. Enter a number or the exact subscription ID/name."
    }
}

function New-RandomBase64 {
    param([int]$Bytes = 32)
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
        return [Convert]::ToBase64String($buffer)
    } finally {
        $rng.Dispose()
    }
}

function Format-ValuePreview {
    param(
        [string]$Value,
        [int]$KeepTail = 5
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "(empty)"
    }

    if ($Value.Length -le 10) {
        return $Value
    }

    $tail = [Math]::Min($KeepTail, $Value.Length)
    return ("*" * ($Value.Length - $tail)) + $Value.Substring($Value.Length - $tail)
}

function Read-TextValue {
    param(
        [string]$Name,
        [string]$Prompt,
        [string]$Default = "",
        [switch]$Required
    )

    $preview = if ($Default -ne "") { " [current: $(Format-ValuePreview -Value $Default)]" } else { "" }
    $label = "$Prompt$preview"
    while ($true) {
        $value = Read-Host $label
        if ([string]::IsNullOrWhiteSpace($value)) {
            if (-not [string]::IsNullOrWhiteSpace($Default)) {
                return $Default.Trim()
            }
            $value = $Default
        }
        if (-not $Required -or -not [string]::IsNullOrWhiteSpace($value)) {
            return $value.Trim()
        }
        Write-Warn "$Name is required."
    }
}

function Read-SecretValue {
    [CmdletBinding()]
    param(
        [string]$Name,
        [string]$Description,
        [bool]$Exists,
        [int]$GenerateBytes = 0,
        [switch]$Required
    )

    if ($Exists) {
        return $null
    }

    if ($GenerateBytes -gt 0) {
        return New-RandomBase64 -Bytes $GenerateBytes
    }

    if (-not $Required) {
        return $null
    }

    while ($true) {
        $secure = Read-Host "Paste value for $Name" -AsSecureString
        $plain = ConvertFrom-SecureStringToPlainText -Value $secure
        if (-not [string]::IsNullOrWhiteSpace($plain) -or -not $Required) {
            return $plain
        }
        Write-Warn "$Name is required."
    }
}

function Invoke-Gh {
    param([string[]]$Arguments)
    & gh @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gh $($Arguments -join ' ') failed."
    }
}

function Start-GitHubWorkflow {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$RepoName,
        [string]$Workflow,
        [string]$Ref = "main",
        [hashtable]$Inputs = @{}
    )

    $args = @("workflow", "run", $Workflow, "--repo", $RepoName, "--ref", $Ref)
    foreach ($entry in $Inputs.GetEnumerator()) {
        $args += @("-f", "$($entry.Key)=$($entry.Value)")
    }

    if ($PSCmdlet.ShouldProcess($RepoName, "dispatch workflow $Workflow")) {
        Invoke-Gh -Arguments $args
    }
}

function Get-DesiredTextValue {
    [CmdletBinding()]
    param(
        [string]$Name,
        [string]$ExistingValue,
        [string]$DefaultValue = "",
        [switch]$PromptIfMissing
    )

    if (-not [string]::IsNullOrWhiteSpace($ExistingValue)) {
        Write-Info "Keeping existing $Name = $ExistingValue"
        return $ExistingValue.Trim()
    }

    if (-not [string]::IsNullOrWhiteSpace($DefaultValue)) {
        Write-Info "Using derived $Name = $DefaultValue"
        return $DefaultValue.Trim()
    }

    if ($PromptIfMissing) {
        return Read-TextValue -Name $Name -Prompt $Name -Required
    }

    return ""
}

function Invoke-AzJson {
    param([string[]]$Arguments)
    $json = & az @Arguments -o json 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) {
        return $null
    }
    return $json | ConvertFrom-Json
}

function Set-GitHubSecret {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$Name,
        [string]$Value,
        [string]$RepoName
    )
    if ($null -eq $Value) { return $false }
    if ($PSCmdlet.ShouldProcess($RepoName, "set GitHub secret $Name")) {
        $Value | gh secret set $Name --repo $RepoName | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to set GitHub secret $Name." }
    }
    return $true
}

function Set-GitHubVariable {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$Name,
        [string]$Value,
        [string]$RepoName
    )
    if ($null -eq $Value) { return $false }
    if ($PSCmdlet.ShouldProcess($RepoName, "set GitHub variable $Name")) {
        Invoke-Gh -Arguments @("variable", "set", $Name, "--repo", $RepoName, "--body", $Value)
    }
    return $true
}

function New-GitHubAppViaManifest {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$AppName,
        [string]$RepoName,
        [string]$HomepageUrl,
        [int[]]$TryPorts = @(3000, 3001, 3002, 8080, 8081)
    )

    $port = $null
    foreach ($candidatePort in $TryPorts) {
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidatePort)
            $listener.Start()
            $listener.Stop()
            $port = $candidatePort
            break
        } catch {
            continue
        }
    }

    if (-not $port) {
        throw "No available local port in [$($TryPorts -join ', ')]. Free a port and retry."
    }

    $callbackUrl = "http://localhost:$port/callback"
    $state = [System.Guid]::NewGuid().ToString("N")

    $manifestObj = [ordered]@{
        name = $AppName
        url = $HomepageUrl
        redirect_url = $callbackUrl
        public = $false
        default_permissions = [ordered]@{
            contents = "read"
            metadata = "read"
            actions = "write"
        }
        default_events = @()
    }

    $manifestJson = $manifestObj | ConvertTo-Json -Compress -Depth 5
    $manifestHtmlSafe = $manifestJson -replace '&','&amp;' -replace '"','&quot;'

    $launchHtml = @"
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Creating CNA App...</title></head>
<body style="font-family:sans-serif;padding:2em;background:#0d1117;color:#e6edf3">
  <h2 style="color:#58a6ff">Creating GitHub App: $AppName</h2>
  <p>Submitting the app manifest to GitHub. A pre-filled creation form will open next.</p>
  <p style="color:#8b949e">Click <strong style="color:#3fb950">Create GitHub App</strong> on the GitHub page to continue.</p>
  <form id="f" action="https://github.com/settings/apps/new" method="post">
    <input type="hidden" name="state" value="$state" />
    <input type="hidden" name="manifest" value="$manifestHtmlSafe" />
  </form>
  <script>document.getElementById('f').submit();</script>
</body>
</html>
"@

    $successHtml = @"
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>CNA App Created</title></head>
<body style="font-family:sans-serif;padding:2em;background:#0d1117;color:#e6edf3">
  <h2 style="color:#3fb950">&#x2705; $AppName created successfully</h2>
  <p>You can close this tab and return to the terminal.</p>
</body>
</html>
"@

    $http = [System.Net.HttpListener]::new()
    $http.Prefixes.Add("http://localhost:$port/")
    $http.Start()

    Write-Host ""
    Write-Host "  Opening browser for GitHub App creation." -ForegroundColor Cyan
    Write-Host "  App name    : $AppName" -ForegroundColor White
    Write-Host "  Permissions : Contents(read) · Metadata(read) · Actions(write)" -ForegroundColor White
    Write-Host "  Repo scope  : $RepoName" -ForegroundColor White
    Write-Host ""
    Write-Host "  What you will see in the browser:" -ForegroundColor White
    Write-Host "    • A pre-filled 'Register new GitHub App' form on github.com" -ForegroundColor DarkGray
    Write-Host "    • Click the green 'Create GitHub App' button to continue" -ForegroundColor DarkGray
    Write-Host "    • The script captures the app credentials automatically after creation" -ForegroundColor DarkGray
    Write-Host ""

    if (-not $PSCmdlet.ShouldProcess($AppName, "open browser for GitHub App manifest flow")) {
        $http.Stop()
        Write-Warn "WhatIf: would serve manifest form on http://localhost:$port/ and open browser"
        return $null
    }

    Start-Process "http://localhost:$port/"
    Write-Host "  Waiting for GitHub callback on port $port (3-minute timeout)..." -ForegroundColor DarkGray

    $callbackData = [hashtable]::Synchronized(@{ Code = $null; State = $null; Error = $null })
    $launchHtmlCopy = $launchHtml
    $successHtmlCopy = $successHtml

    $runspace = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
    $runspace.Open()
    $runspace.SessionStateProxy.SetVariable('http', $http)
    $runspace.SessionStateProxy.SetVariable('callbackData', $callbackData)
    $runspace.SessionStateProxy.SetVariable('launchHtml', $launchHtmlCopy)
    $runspace.SessionStateProxy.SetVariable('successHtml', $successHtmlCopy)

    $powerShell = [System.Management.Automation.PowerShell]::Create()
    $powerShell.Runspace = $runspace
    $null = $powerShell.AddScript({
        function Send-Html {
            param($ctx, $body, [int]$status = 200)
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
            $ctx.Response.StatusCode = $status
            $ctx.Response.ContentType = 'text/html; charset=utf-8'
            $ctx.Response.ContentLength64 = $bytes.Length
            $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
            $ctx.Response.OutputStream.Close()
        }

        try {
            while ($true) {
                $ctx = $http.GetContext()
                $path = $ctx.Request.Url.AbsolutePath

                if ($path -eq '/') {
                    Send-Html $ctx $launchHtml
                    continue
                }

                if ($path -eq '/callback') {
                    $queryValues = @{}
                    foreach ($pair in (($ctx.Request.Url.Query.TrimStart('?')) -split '&')) {
                        if ([string]::IsNullOrWhiteSpace($pair)) { continue }
                        $kv = $pair -split '=', 2
                        $key = [Uri]::UnescapeDataString($kv[0])
                        $value = if ($kv.Count -gt 1) { [Uri]::UnescapeDataString($kv[1]) } else { "" }
                        $queryValues[$key] = $value
                    }
                    $callbackData.Code = $queryValues['code']
                    $callbackData.State = $queryValues['state']
                    Send-Html $ctx $successHtml
                    break
                }

                $ctx.Response.StatusCode = 404
                $ctx.Response.Close()
            }
        } catch {
            $callbackData.Error = $_.Exception.Message
        }
    })

    $handle = $powerShell.BeginInvoke()
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($handle.IsCompleted -or $null -ne $callbackData.Code) {
            break
        }
        Start-Sleep -Milliseconds 300
    }

    $http.Stop()
    $powerShell.Dispose()
    $runspace.Close()

    if ($callbackData.Error) {
        throw "Listener error: $($callbackData.Error)"
    }

    $code = $callbackData.Code
    $retState = $callbackData.State
    if ([string]::IsNullOrWhiteSpace($code)) {
        throw "No callback code received within 3 minutes. Re-run the script and click 'Create GitHub App' promptly."
    }
    if ($retState -ne $state) {
        throw "State mismatch in GitHub callback. Re-run the script."
    }

    Write-Step "Exchanging code for GitHub App credentials"
    $ghToken = (& gh auth token 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ghToken)) {
        throw "Could not retrieve GitHub auth token. Ensure 'gh auth login' has been completed."
    }

    $response = Invoke-RestMethod `
        -Uri "https://api.github.com/app-manifests/$code/conversions" `
        -Method Post `
        -Headers @{
            Authorization = "Bearer $ghToken"
            Accept = "application/vnd.github+json"
            "X-GitHub-Api-Version" = "2022-11-28"
        }

    if (-not $response.id -or -not $response.pem) {
        throw "GitHub API did not return App ID or PEM key. Response: $($response | ConvertTo-Json -Depth 3)"
    }

    Write-Ok "GitHub App created: $($response.name) (ID: $([string]$response.id))"
    return [pscustomobject]@{
        AppId = [string]$response.id
        PrivateKey = [string]$response.pem
        Name = [string]$response.name
        Slug = [string]$response.slug
    }
}

function Get-GitHubAppInstallationId {
    param([string]$AppId)

    $installId = & gh api "user/installations" --jq ".installations[] | select(.app_id == $AppId) | .id" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($installId)) {
        return $null
    }

    return [string]$installId.Trim()
}

function Wait-GitHubAppInstallation {
    [CmdletBinding()]
    param(
        [string]$AppId,
        [string]$AppSlug,
        [string]$RepoName,
        [int]$TimeoutMinutes = 3
    )

    $installUrl = "https://github.com/settings/apps/$AppSlug/installations"
    Write-Step "Installing GitHub App on repository"
    Write-Host "  Opening browser for GitHub App installation." -ForegroundColor Cyan
    Write-Host "  Repo scope  : $RepoName" -ForegroundColor White
    Write-Host "  Install URL : $installUrl" -ForegroundColor White
    Write-Host "  Select 'Only select repositories' and choose this repo only." -ForegroundColor Yellow
    Write-Host ""
    Start-Process $installUrl

    $deadline = [DateTime]::UtcNow.AddMinutes($TimeoutMinutes)
    while ([DateTime]::UtcNow -lt $deadline) {
        $installId = Get-GitHubAppInstallationId -AppId $AppId
        if (-not [string]::IsNullOrWhiteSpace($installId)) {
            Write-Ok "GitHub App installation confirmed: $installId"
            return $installId
        }
        Start-Sleep -Seconds 5
    }

    throw "GitHub App installation was not confirmed within $TimeoutMinutes minutes. Re-run the script after installing it on the repository."
}

function Get-ExistingGitHubSecretNames {
    param([string]$RepoName)
    $names = @{}
    $json = & gh secret list --repo $RepoName --json name 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) { return $names }
    foreach ($item in ($json | ConvertFrom-Json)) {
        $names[$item.name] = $true
    }
    return $names
}

function Get-ExistingGitHubVariableValues {
    param([string]$RepoName)
    $values = @{}
    $json = & gh variable list --repo $RepoName --json name,value 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) { return $values }
    foreach ($item in ($json | ConvertFrom-Json)) {
        $values[$item.name] = [string]$item.value
    }
    return $values
}

function Get-SafeFederatedCredentialName {
    param([string]$RepoName, [string]$Label)
    $name = "cna-$($RepoName -replace '[^A-Za-z0-9-]', '-')-$($Label -replace '[^A-Za-z0-9-]', '-')"
    if ($name.Length -gt 120) {
        return $name.Substring(0, 120)
    }
    return $name
}

function Get-GitHubEnvironments {
    param([string]$RepoName)

    $json = & gh api "repos/$RepoName/environments" --jq '.environments[].name' 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) {
        return @()
    }

    return @($json -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
}

function Ensure-GitHubEnvironment {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$RepoName,
        [string]$EnvironmentName
    )

    $existingEnvironments = Get-GitHubEnvironments -RepoName $RepoName
    if ($existingEnvironments -contains $EnvironmentName) {
        Write-Ok "GitHub environment exists: $EnvironmentName"
        return $false
    }

    if ($PSCmdlet.ShouldProcess($RepoName, "create GitHub environment $EnvironmentName")) {
        Invoke-Gh -Arguments @("api", "-X", "PUT", "repos/$RepoName/environments/$EnvironmentName") | Out-Null
    }
    Write-Ok "Created GitHub environment: $EnvironmentName"
    return $true
}

function Write-BootstrapReport {
    [CmdletBinding()]
    param(
        [string]$Path,
        [object]$Account,
        [string]$RepoName,
        [string]$BranchName,
        [string]$EnvironmentName,
        [string]$AppDisplayName,
        [string]$AppId,
        [string]$TenantId,
        [string[]]$GitHubEnvironments,
        [string]$WorkloadResourceGroup,
        [string]$WorkloadResourceGroupStatus,
        [string]$TfstateResourceGroup,
        [string]$TfstateResourceGroupStatus,
        [string]$TfstateStorageAccount,
        [string]$TfstateStorageAccountStatus,
        [string]$TfstateContainer,
        [string]$TfstateContainerStatus,
        [string]$TfstateStorageRoleStatus,
        [string]$GitHubAppName,
        [string]$GitHubAppId,
        [string]$GitHubAppSlug,
        [string]$GitHubAppInstallationId,
        [string]$GitHubAppStatus,
        [int]$SecretsSet,
        [int]$SecretsKept,
        [int]$VariablesSet,
        [string[]]$CreatedGitHubEnvironments,
        [string[]]$FederatedCredentials,
        [string]$BootstrapLocation,
        [string]$BootstrapRegionShort
    )

    $reportDir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }

    $createdEnvsText = if ($CreatedGitHubEnvironments.Count -gt 0) { ($CreatedGitHubEnvironments -join ", ") } else { "none" }
    $credentialsText = if ($FederatedCredentials.Count -gt 0) { ($FederatedCredentials -join "`n") } else { "none" }

    $content = @"
# CNA Bootstrap Report

- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
- Repository: $RepoName
- Branch: $BranchName
- Environment: $EnvironmentName
- Azure subscription: $($Account.name) ($($Account.id))
- Azure tenant: $TenantId
- Entra app display name: $AppDisplayName
- Entra app client ID: $AppId
- GitHub App name: $GitHubAppName
- GitHub App status: $GitHubAppStatus
- GitHub App ID: $GitHubAppId
- GitHub App slug: $GitHubAppSlug
- GitHub App installation ID: $GitHubAppInstallationId
- Bootstrap location: $BootstrapLocation
- Bootstrap region short: $BootstrapRegionShort

## GitHub Integration

| Item | Value |
| --- | --- |
| GitHub environments present | $(@($GitHubEnvironments) -join ", ") |
| GitHub environments ensured | $createdEnvsText |
| Federated credential subjects | `$(($FederatedCredentials.Count))` |
| GitHub App status | $GitHubAppStatus |
| GitHub App installation | $GitHubAppInstallationId |
| Secrets written | `$SecretsSet` |
| Secrets kept/skipped | `$SecretsKept` |
| Variables written | `$VariablesSet` |

## Azure Resources

| Resource | Value |
| --- | --- |
| Workload RG | `$WorkloadResourceGroup` (`$WorkloadResourceGroupStatus`) |
| Tfstate RG | `$TfstateResourceGroup` (`$TfstateResourceGroupStatus`) |
| Tfstate storage account | `$TfstateStorageAccount` (`$TfstateStorageAccountStatus`) |
| Tfstate container | `$TfstateContainer` (`$TfstateContainerStatus`) |
| Tfstate storage role | `$TfstateStorageRoleStatus` |

## Federated Credentials

`$credentialsText`

## CAF / Naming Notes

- Workload and platform resources stay in the CAF-style workload RG: `$WorkloadResourceGroup`
- Terraform state remains in a separate CAF-named backend RG: `$TfstateResourceGroup`
- GitHub OIDC subjects are created for the selected branch and GitHub environments
- GitHub App creation follows the manifest flow and scopes the installation to this repository

## Next Steps

1. Run workflow `100-validate-prereqs.yml`.
2. Run workflow `200-build-images.yml`.
3. Run workflow `210-deploy-azure.yml`.
4. Review workflow `110-sync-keys.yml` after Key Vault is available.
"@

    Set-Content -Path $Path -Value $content -Encoding UTF8
    Write-Ok "Wrote bootstrap report: $Path"
}

function Add-GitHubFederatedCredential {
    param(
        [string]$AppId,
        [string]$Name,
        [string]$Subject
    )

    $existingCredential = & az ad app federated-credential list --id $AppId --query "[?name=='$Name'].id" -o tsv 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($existingCredential)) {
        Write-Ok "Federated credential exists: $Name"
        return
    }

    $credential = @{
        name      = $Name
        issuer    = "https://token.actions.githubusercontent.com"
        subject   = $Subject
        audiences = @("api://AzureADTokenExchange")
    } | ConvertTo-Json -Compress

    $credentialFile = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -Path $credentialFile -Value $credential -Encoding UTF8
        $credentialArg = "@$credentialFile"
        & az ad app federated-credential create --id $AppId --parameters "$credentialArg" --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to create federated credential $Name." }
        Write-Ok "Created federated credential: $Name"
    }
    finally {
        Remove-Item -Path $credentialFile -Force -ErrorAction SilentlyContinue
    }
}

function Get-AvailableStorageAccountName {
    [CmdletBinding()]
    param(
        [string]$BaseName,
        [string]$ResourceGroupName
    )

    $candidate = ($BaseName.ToLowerInvariant() -replace '[^a-z0-9]', '')
    if ($candidate.Length -gt 24) {
        $candidate = $candidate.Substring(0, 24)
    }

    for ($i = 0; $i -lt 20; $i++) {
        $name = if ($i -eq 0) {
            $candidate
        } else {
            $suffix = "{0:x2}" -f $i
            $prefixLength = [Math]::Min(24 - $suffix.Length, $candidate.Length)
            $candidate.Substring(0, $prefixLength) + $suffix
        }

        $existingId = & az storage account show --name $name --resource-group $ResourceGroupName --query id -o tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($existingId)) {
            return $name
        }

        $nameAvailable = & az storage account check-name --name $name --query nameAvailable -o tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and $nameAvailable -eq "true") {
            return $name
        }
    }

    throw "Unable to find an available storage account name derived from '$BaseName'."
}

function Ensure-ResourceGroup {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$SubscriptionId,
        [string]$Location,
        [string]$ResourceGroupName,
        [string]$PurposeLabel
    )

    $exists = & az group exists --name $ResourceGroupName --subscription $SubscriptionId --output tsv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to determine whether resource group '$ResourceGroupName' exists."
    }

    if ($exists -ne "true") {
        if ($PSCmdlet.ShouldProcess($ResourceGroupName, "create $PurposeLabel resource group")) {
            & az group create --name $ResourceGroupName --location $Location --subscription $SubscriptionId --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create resource group '$ResourceGroupName'." }
        }
        Write-Ok "Created $PurposeLabel resource group: $ResourceGroupName"
        return "created"
    } else {
        Write-Ok "$PurposeLabel resource group exists: $ResourceGroupName"
        return "existing"
    }
}

function Ensure-TfstateBackendResources {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$SubscriptionId,
        [string]$Location,
        [string]$ResourceGroupName,
        [string]$StorageAccountName,
        [string]$ContainerName,
        [string]$ClientId
    )

    Write-Step "Ensuring Terraform backend prerequisites"
    $resourceGroupStatus = Ensure-ResourceGroup -SubscriptionId $SubscriptionId -Location $Location -ResourceGroupName $ResourceGroupName -PurposeLabel "tfstate"

    $storageId = & az storage account show --name $StorageAccountName --resource-group $ResourceGroupName --subscription $SubscriptionId --query id -o tsv 2>$null
    $storageAccountStatus = "existing"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($storageId)) {
        if ($PSCmdlet.ShouldProcess($StorageAccountName, "create tfstate storage account")) {
            & az storage account create `
                --name $StorageAccountName `
                --resource-group $ResourceGroupName `
                --subscription $SubscriptionId `
                --location $Location `
                --sku Standard_LRS `
                --min-tls-version TLS1_2 `
                --allow-blob-public-access false `
                --https-only true `
                --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create tfstate storage account '$StorageAccountName'." }
        }
        Write-Ok "Created tfstate storage account: $StorageAccountName"
        $storageAccountStatus = "created"
        $storageId = & az storage account show --name $StorageAccountName --resource-group $ResourceGroupName --subscription $SubscriptionId --query id -o tsv
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($storageId)) {
            throw "Failed to resolve storage account ID for '$StorageAccountName' after creation."
        }
    } else {
        Write-Ok "Tfstate storage account exists: $StorageAccountName"
    }

    $accountKey = & az storage account keys list `
        --resource-group $ResourceGroupName `
        --subscription $SubscriptionId `
        --account-name $StorageAccountName `
        --query "[0].value" `
        --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accountKey)) {
        throw "Failed to read storage account key for '$StorageAccountName'."
    }

    & az storage container show --name $ContainerName --account-name $StorageAccountName --account-key $accountKey --output none 2>$null
    $containerStatus = "existing"
    if ($LASTEXITCODE -ne 0) {
        if ($PSCmdlet.ShouldProcess($ContainerName, "create tfstate blob container")) {
            & az storage container create --name $ContainerName --account-name $StorageAccountName --account-key $accountKey --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create tfstate blob container '$ContainerName'." }
        }
        Write-Ok "Created tfstate blob container: $ContainerName"
        $containerStatus = "created"
    } else {
        Write-Ok "Tfstate blob container exists: $ContainerName"
    }

    $storageRoleStatus = "unknown"
    $clientObjectId = & az ad sp show --id $ClientId --query id --output tsv 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($clientObjectId)) {
        $assignmentCount = & az role assignment list `
            --assignee-object-id $clientObjectId `
            --scope $storageId `
            --subscription $SubscriptionId `
            --query "[?roleDefinitionName=='Storage Blob Data Contributor'] | length(@)" `
            --output tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and $assignmentCount -eq "0") {
            if ($PSCmdlet.ShouldProcess($StorageAccountName, "assign Storage Blob Data Contributor to CI identity")) {
                & az role assignment create `
                    --role "Storage Blob Data Contributor" `
                    --assignee-object-id $clientObjectId `
                    --assignee-principal-type ServicePrincipal `
                    --scope $storageId `
                    --subscription $SubscriptionId `
                    --output none
                if ($LASTEXITCODE -ne 0) { throw "Failed to assign Storage Blob Data Contributor on '$StorageAccountName'." }
            }
            Write-Ok "Assigned Storage Blob Data Contributor to CI identity"
            $storageRoleStatus = "created"
        } else {
            Write-Ok "CI identity already has Storage Blob Data Contributor on tfstate storage"
            $storageRoleStatus = "existing"
        }
    } else {
        Write-Warn "Could not resolve service principal object ID for $ClientId. Workflow 000 may need to assign storage RBAC itself."
    }

    return [pscustomobject]@{
        ResourceGroupStatus  = $resourceGroupStatus
        StorageAccountStatus  = $storageAccountStatus
        ContainerStatus       = $containerStatus
        StorageRoleStatus     = $storageRoleStatus
    }
}

Write-Step "Checking local prerequisites"
Assert-Command "gh"
if (-not $SkipAzureSetup) {
    Assert-Command "az"
}

if (-not $Repo) {
    $Repo = (& gh repo view --json nameWithOwner -q .nameWithOwner 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Repo)) {
        $Repo = Read-TextValue -Name "Repo" -Prompt "GitHub repo in owner/name format" -Required
    }
}
Write-Ok "GitHub repo: $Repo"

if (-not $AppDisplayName) {
    $AppDisplayName = "CNA Assessment Tool"
    Write-Info "Using default Entra app display name: $AppDisplayName"
}

Invoke-Gh -Arguments @("auth", "status")
$existingSecrets = Get-ExistingGitHubSecretNames -RepoName $Repo
$existingVariables = Get-ExistingGitHubVariableValues -RepoName $Repo
$createdGitHubEnvironments = [System.Collections.Generic.List[string]]::new()
foreach ($environmentName in @("dev", "prod")) {
    if (Ensure-GitHubEnvironment -RepoName $Repo -EnvironmentName $environmentName) {
        $createdGitHubEnvironments.Add($environmentName) | Out-Null
    }
}
$githubEnvironments = Get-GitHubEnvironments -RepoName $Repo

$githubAppName = "CNA Assessment Tool"
$githubAppId = ""
$githubAppSlug = ""
$githubAppInstallationId = ""
$githubAppStatus = "not-configured"
$hasGitHubAppId = $existingSecrets.ContainsKey("GH_APP_ID")
$hasGitHubAppPrivateKey = $existingSecrets.ContainsKey("GH_APP_PRIVATE_KEY")
if ($hasGitHubAppId -xor $hasGitHubAppPrivateKey) {
    throw "GitHub App secrets are partially configured. Set both GH_APP_ID and GH_APP_PRIVATE_KEY, or neither."
}
if (-not ($hasGitHubAppId -and $hasGitHubAppPrivateKey)) {
    Write-Step "Creating GitHub App"
    $repoUrl = "https://github.com/$Repo"
    $githubApp = New-GitHubAppViaManifest -AppName $githubAppName -RepoName $Repo -HomepageUrl $repoUrl
    $githubAppId = $githubApp.AppId
    $githubAppSlug = $githubApp.Slug
    $githubAppInstallationId = Wait-GitHubAppInstallation -AppId $githubAppId -AppSlug $githubAppSlug -RepoName $Repo
    $githubAppStatus = "created"
} else {
    Write-Ok "GitHub App secrets already exist; skipping creation."
    $githubAppStatus = "already-configured"
}

$tenantId = ""
$resolvedSubscriptionId = ""
$resolvedSubscriptionName = ""
$appId = ""
$entraClientSecret = $null
$federatedCredentialSubjects = [System.Collections.Generic.List[string]]::new()

if (-not $SkipAzureSetup) {
    Write-Step "Preparing Azure OIDC app registration"
    $account = Initialize-AzLogin

    $account = Select-AzSubscription -CurrentAccount $account
    & az account set --subscription $account.id | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to switch to subscription $($account.id)."
    }
    $account = Invoke-AzJson -Arguments @("account", "show")

    $tenantId = [string]$account.tenantId
    $resolvedSubscriptionId = [string]$account.id
    $resolvedSubscriptionName = [string]$account.name
    Write-Ok "Azure subscription: $($account.name) ($resolvedSubscriptionId)"
    Write-Ok "Azure tenant: $tenantId"

    $existingApp = & az ad app list --display-name $AppDisplayName --query "[0].appId" -o tsv 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($existingApp)) {
        $appId = $existingApp.Trim()
        Write-Ok "Using existing app registration: $AppDisplayName ($appId)"
    } else {
        if ($PSCmdlet.ShouldProcess($AppDisplayName, "create Entra app registration")) {
            $appId = (& az ad app create --display-name $AppDisplayName --query appId -o tsv).Trim()
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($appId)) {
                throw "Failed to create Entra app registration."
            }
        }
        Write-Ok "Created app registration: $AppDisplayName ($appId)"
    }

    $sp = & az ad sp list --filter "appId eq '$appId'" --query "[0].id" -o tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sp)) {
        if ($PSCmdlet.ShouldProcess($appId, "create service principal")) {
            & az ad sp create --id $appId --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create service principal." }
            Start-Sleep -Seconds 10
        }
        Write-Ok "Created service principal"
    } else {
        Write-Ok "Service principal exists"
    }

    $scope = "/subscriptions/$resolvedSubscriptionId"
    foreach ($role in @("Contributor", "User Access Administrator")) {
        $assignment = & az role assignment list --assignee $appId --role $role --scope $scope --query "[0].id" -o tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($assignment)) {
            Write-Ok "Role already assigned: $role"
            continue
        }
        if ($PSCmdlet.ShouldProcess($scope, "assign $role to $appId")) {
            & az role assignment create --role $role --assignee $appId --scope $scope --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to assign $role." }
        }
        Write-Ok "Assigned role: $role"
    }

    $subjects = @(
        "repo:$Repo`:ref:refs/heads/$Branch"
    )

    $environmentNames = Get-GitHubEnvironments -RepoName $Repo
    foreach ($environmentName in $environmentNames) {
        $subjects += "repo:$Repo`:environment:$environmentName"
    }

    foreach ($subject in ($subjects | Sort-Object -Unique)) {
        $federatedCredentialSubjects.Add($subject) | Out-Null
        $subjectLabel = if ($subject -match ':environment:(.+)$') {
            "env-$($Matches[1])"
        } else {
            "ref-$Branch"
        }
        $credentialName = Get-SafeFederatedCredentialName -RepoName $Repo -Label $subjectLabel
        if ($PSCmdlet.ShouldProcess($appId, "ensure GitHub OIDC federated credential for $subject")) {
            Add-GitHubFederatedCredential -AppId $appId -Name $credentialName -Subject $subject
        }
    }

    $nextAuthUrlForRedirect = if ($existingVariables.ContainsKey("CNA_NEXTAUTH_URL")) {
        [string]$existingVariables["CNA_NEXTAUTH_URL"]
    } else {
        "none"
    }
    Write-Info "Using CNA_NEXTAUTH_URL = $nextAuthUrlForRedirect"
    if ($nextAuthUrlForRedirect -ne "none") {
        if (-not ($nextAuthUrlForRedirect -match '^https?://')) {
            throw "CNA_NEXTAUTH_URL must be 'none' or start with http:// or https://."
        }
        $redirectUri = "$($nextAuthUrlForRedirect.TrimEnd('/'))/api/auth/callback/microsoft-entra-id"
        $app = Invoke-AzJson -Arguments @("ad", "app", "show", "--id", $appId)
        $redirectUris = @($app.web.redirectUris)
        if (-not ($redirectUris -contains $redirectUri)) {
            $updatedUris = @($redirectUris + $redirectUri)
            if ($PSCmdlet.ShouldProcess($appId, "add redirect URI $redirectUri")) {
                & az ad app update --id $appId --web-redirect-uris @updatedUris --output none
                if ($LASTEXITCODE -ne 0) { throw "Failed to update redirect URI." }
            }
            Write-Ok "Added redirect URI: $redirectUri"
        } else {
            Write-Ok "Redirect URI already present: $redirectUri"
        }
    } else {
        Write-Host "    [INFO] CNA_NEXTAUTH_URL is 'none'. Redirect URI will be added later after workflow 210 exposes the real Front Door hostname."
    }
} else {
    Write-Step "Collecting Azure values without Azure setup"
    $appId = Read-TextValue -Name "AZURE_CLIENT_ID" -Prompt "Azure OIDC app registration client ID" -Required
    $tenantId = Read-TextValue -Name "AZURE_TENANT_ID" -Prompt "Azure tenant ID" -Required
    $resolvedSubscriptionId = Read-TextValue -Name "AZURE_SUBSCRIPTION_ID" -Prompt "Azure subscription ID" -Required
    $resolvedSubscriptionName = Read-TextValue -Name "AZURE_TARGET_SUBSCRIPTION_NAME" -Prompt "Azure subscription name (optional, for human-readable validation)" -Default "none"
    $nextAuthUrlForRedirect = if ($existingVariables.ContainsKey("CNA_NEXTAUTH_URL")) { [string]$existingVariables["CNA_NEXTAUTH_URL"] } else { "none" }
}

Write-Step "Collecting GitHub secret values"

if ($githubAppStatus -eq "created") {
    $secretValues = [ordered]@{}
    $secretValues["GH_APP_ID"] = $githubAppId
    $secretValues["GH_APP_PRIVATE_KEY"] = $githubApp.PrivateKey
} else {
    $secretValues = [ordered]@{}
}

if (-not $existingSecrets.ContainsKey("CNA_ENTRA_CLIENT_SECRET")) {
    if (-not $SkipAzureSetup) {
        if ($PSCmdlet.ShouldProcess($appId, "create Entra client secret for NextAuth")) {
            $entraClientSecret = (& az ad app credential reset --id $appId --append --display-name "cna-nextauth-$Environment-$(Get-Date -Format yyyyMMddHHmmss)" --years 2 --query password -o tsv).Trim()
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($entraClientSecret)) {
                throw "Failed to create Entra client secret."
            }
        }
        Write-Ok "Created Entra client secret for NextAuth"
    }
}
if ($null -eq $entraClientSecret) {
    $entraClientSecret = Read-SecretValue -Name "CNA_ENTRA_CLIENT_SECRET" -Description "Entra OAuth client secret used by NextAuth" -Exists $existingSecrets.ContainsKey("CNA_ENTRA_CLIENT_SECRET") -Required
}

$secretValues["AZURE_CLIENT_ID"] = $appId
$secretValues["AZURE_TENANT_ID"] = $tenantId
$secretValues["AZURE_SUBSCRIPTION_ID"] = $resolvedSubscriptionId
$secretValues["CNA_ENTRA_CLIENT_SECRET"] = $entraClientSecret
$secretValues["CNA_POSTGRES_ADMIN_PASSWORD"] = Read-SecretValue -Name "CNA_POSTGRES_ADMIN_PASSWORD" -Description "PostgreSQL admin password" -Exists $existingSecrets.ContainsKey("CNA_POSTGRES_ADMIN_PASSWORD") -GenerateBytes 18 -Required
$secretValues["CNA_NEXTAUTH_SECRET"] = Read-SecretValue -Name "CNA_NEXTAUTH_SECRET" -Description "Auth.js signing secret" -Exists $existingSecrets.ContainsKey("CNA_NEXTAUTH_SECRET") -GenerateBytes 32 -Required
$secretValues["CNA_CREDENTIAL_ENCRYPTION_KEY"] = Read-SecretValue -Name "CNA_CREDENTIAL_ENCRYPTION_KEY" -Description "base64 32-byte AES key for stored cloud credentials" -Exists $existingSecrets.ContainsKey("CNA_CREDENTIAL_ENCRYPTION_KEY") -GenerateBytes 32 -Required
$secretValues["GHCR_PAT"] = Read-SecretValue -Name "GHCR_PAT" -Description "GitHub PAT with read:packages for Container Apps image pulls" -Exists $existingSecrets.ContainsKey("GHCR_PAT") -Required
$secretValues["FRONTDOOR_CERTIFICATE_PFX_PASSWORD"] = Read-SecretValue -Name "FRONTDOOR_CERTIFICATE_PFX_PASSWORD" -Description "optional custom TLS certificate PFX password" -Exists $existingSecrets.ContainsKey("FRONTDOOR_CERTIFICATE_PFX_PASSWORD")
$secretValues["CNA_AWS_ROLE_ARN"] = Read-SecretValue -Name "CNA_AWS_ROLE_ARN" -Description "optional AWS OIDC role ARN for portal publishing" -Exists $existingSecrets.ContainsKey("CNA_AWS_ROLE_ARN")
$secretValues["CNA_PUBLISH_BUCKET"] = Read-SecretValue -Name "CNA_PUBLISH_BUCKET" -Description "optional S3 bucket for portal publishing" -Exists $existingSecrets.ContainsKey("CNA_PUBLISH_BUCKET")

Write-Step "Collecting GitHub variable values"
$storageSuffix = ($resolvedSubscriptionId -replace '[^A-Za-z0-9]', '')
if ($storageSuffix.Length -gt 6) { $storageSuffix = $storageSuffix.Substring(0, 6) }
if ([string]::IsNullOrWhiteSpace($storageSuffix)) { $storageSuffix = "state" }
$defaultTfstateStorage = "stcna$($storageSuffix.ToLowerInvariant())tfstate"
if ($defaultTfstateStorage.Length -gt 24) { $defaultTfstateStorage = $defaultTfstateStorage.Substring(0, 24) }

$resolvedDrawioMcpUrl = if ([string]::IsNullOrWhiteSpace($nextAuthUrlForRedirect) -or $nextAuthUrlForRedirect -eq "none") {
    "none"
} else {
    "$($nextAuthUrlForRedirect.TrimEnd('/'))/api/drawio-mcp"
}

$variableDefaults = [ordered]@{
    TFSTATE_RESOURCE_GROUP         = "rg-cna-$Environment-scus-tfstate"
    TFSTATE_STORAGE_ACCOUNT        = $defaultTfstateStorage
    TFSTATE_CONTAINER              = "tfstate"
    AZURE_TARGET_SUBSCRIPTION_NAME = $(if ([string]::IsNullOrWhiteSpace($resolvedSubscriptionName)) { "none" } else { $resolvedSubscriptionName })
    CNA_ENTRA_CLIENT_ID            = $appId
    CNA_NEXTAUTH_URL               = $nextAuthUrlForRedirect
    CNA_AI_ENGINE_DEFAULT          = "foundry-claude"
    FOUNDRY_CLAUDE_ENDPOINT        = "none"
    FOUNDRY_CLAUDE_MODEL           = "claude-sonnet-4-6"
    CNA_AZURE_MCP_ENDPOINT         = "https://mcp.azure.com"
    CNA_AZURE_MCP_TRANSPORT        = "streamable-http"
    CNA_AWS_MCP_ENDPOINT           = "https://aws-mcp.us-east-1.api.aws/mcp"
    CNA_AWS_MCP_TRANSPORT          = "streamable-http"
    CNA_DRAWIO_MCP_URL             = $resolvedDrawioMcpUrl
    APPLICATION_INSIGHTS_NAME      = "none"
    KEY_VAULT_NAME                 = "none"
    FRONTDOOR_CERTIFICATE_NAME     = "none"
    FRONTDOOR_CERTIFICATE_PFX_PATH = "none"
}

$variableValues = [ordered]@{}
foreach ($entry in $variableDefaults.GetEnumerator()) {
    $exists = $existingVariables.ContainsKey($entry.Key)
    $existingValue = if ($exists) { [string]$existingVariables[$entry.Key] } else { "" }
    $variableValues[$entry.Key] = Get-DesiredTextValue -Name $entry.Key -ExistingValue $existingValue -DefaultValue ([string]$entry.Value)
}

$bootstrapWorkloadResourceGroup = "rg-cna-$Environment-$BootstrapRegionShort"
$bootstrapTfstateResourceGroup = [string]$variableValues["TFSTATE_RESOURCE_GROUP"]
$bootstrapTfstateContainer = [string]$variableValues["TFSTATE_CONTAINER"]
$bootstrapTfstateStorageAccount = Get-AvailableStorageAccountName -BaseName ([string]$variableValues["TFSTATE_STORAGE_ACCOUNT"]) -ResourceGroupName $bootstrapTfstateResourceGroup
$variableValues["TFSTATE_STORAGE_ACCOUNT"] = $bootstrapTfstateStorageAccount
Write-Info "Resolved TFSTATE_STORAGE_ACCOUNT = $bootstrapTfstateStorageAccount"
$bootstrapWorkloadResourceGroupStatus = "not-run"
$bootstrapTfstateResourceStatus = [pscustomobject]@{
    ResourceGroupStatus  = "not-run"
    StorageAccountStatus = "not-run"
    ContainerStatus      = "not-run"
    StorageRoleStatus    = "not-run"
}

Write-Step "Writing GitHub Secrets"
$setSecretCount = 0
$keptSecretCount = 0
foreach ($entry in $secretValues.GetEnumerator()) {
    if ($null -eq $entry.Value) {
        $keptSecretCount++
        Write-Host "    [KEEP/SKIP] $($entry.Key)"
        continue
    }
    if (Set-GitHubSecret -Name $entry.Key -Value $entry.Value -RepoName $Repo) {
        $setSecretCount++
        Write-Ok "Set secret: $($entry.Key)"
    }
}

Write-Step "Writing GitHub Variables"
$setVariableCount = 0
foreach ($entry in $variableValues.GetEnumerator()) {
    if (Set-GitHubVariable -Name $entry.Key -Value $entry.Value -RepoName $Repo) {
        $setVariableCount++
        Write-Ok "Set variable: $($entry.Key) = $($entry.Value)"
    }
}

if (-not $SkipAzureSetup) {
    Write-Step "Ensuring workload resource group"
    $bootstrapWorkloadResourceGroupStatus = Ensure-ResourceGroup `
        -SubscriptionId $resolvedSubscriptionId `
        -Location $BootstrapLocation `
        -ResourceGroupName $bootstrapWorkloadResourceGroup `
        -PurposeLabel "workload"

    $bootstrapTfstateResourceStatus = Ensure-TfstateBackendResources `
        -SubscriptionId $resolvedSubscriptionId `
        -Location $BootstrapLocation `
        -ResourceGroupName $bootstrapTfstateResourceGroup `
        -StorageAccountName $bootstrapTfstateStorageAccount `
        -ContainerName $bootstrapTfstateContainer `
        -ClientId $appId
}

if (-not $SkipBootstrapDispatch) {
    Write-Step "Dispatching workflow 000 bootstrap"
    Start-GitHubWorkflow -RepoName $Repo -Workflow "000-bootstrap-backend.yml" -Ref $Branch -Inputs @{
        environment              = $Environment
        location                 = $BootstrapLocation
        region_short             = $BootstrapRegionShort
        tfstate_resource_group   = $bootstrapTfstateResourceGroup
        tfstate_storage_account  = $bootstrapTfstateStorageAccount
        tfstate_container        = $bootstrapTfstateContainer
    }
    Write-Ok "Dispatched 000-bootstrap-backend.yml for environment '$Environment'"
}

Write-BootstrapReport -Path (Join-Path $ReportDirectory "$((Get-Date).ToString('yyyyMMdd-HHmmss'))-$Environment-bootstrap-report.md") `
    -Account $account `
    -RepoName $Repo `
    -BranchName $Branch `
    -EnvironmentName $Environment `
    -AppDisplayName $AppDisplayName `
    -AppId $appId `
    -TenantId $tenantId `
    -GitHubEnvironments @($githubEnvironments) `
    -WorkloadResourceGroup $bootstrapWorkloadResourceGroup `
    -WorkloadResourceGroupStatus $bootstrapWorkloadResourceGroupStatus `
    -TfstateResourceGroup $bootstrapTfstateResourceGroup `
    -TfstateResourceGroupStatus $bootstrapTfstateResourceStatus.ResourceGroupStatus `
    -TfstateStorageAccount $bootstrapTfstateStorageAccount `
    -TfstateStorageAccountStatus $bootstrapTfstateResourceStatus.StorageAccountStatus `
    -TfstateContainer $bootstrapTfstateContainer `
    -TfstateContainerStatus $bootstrapTfstateResourceStatus.ContainerStatus `
    -TfstateStorageRoleStatus $bootstrapTfstateResourceStatus.StorageRoleStatus `
    -GitHubAppName $githubAppName `
    -GitHubAppId $githubAppId `
    -GitHubAppSlug $githubAppSlug `
    -GitHubAppInstallationId $githubAppInstallationId `
    -GitHubAppStatus $githubAppStatus `
    -SecretsSet $setSecretCount `
    -SecretsKept $keptSecretCount `
    -VariablesSet $setVariableCount `
    -CreatedGitHubEnvironments @($createdGitHubEnvironments) `
    -FederatedCredentials @($federatedCredentialSubjects) `
    -BootstrapLocation $BootstrapLocation `
    -BootstrapRegionShort $BootstrapRegionShort

Write-Step "Summary"
Write-Host "Repository:       $Repo"
Write-Host "Branch:           $Branch"
Write-Host "Environment:      $Environment"
Write-Host "App registration: $AppDisplayName ($appId)"
Write-Host "GitHub App:       $githubAppName ($githubAppStatus)"
    Write-Host "Workload RG:      $bootstrapWorkloadResourceGroup"
    Write-Host "Tfstate RG:       $bootstrapTfstateResourceGroup"
    Write-Host "Secrets set:      $setSecretCount"
    Write-Host "Secrets kept/skipped: $keptSecretCount"
    Write-Host "Variables set:    $setVariableCount"
    Write-Host "Workload RG status: $bootstrapWorkloadResourceGroupStatus"
    Write-Host "Tfstate RG status:  $($bootstrapTfstateResourceStatus.ResourceGroupStatus)"
    Write-Host "Tfstate account status: $($bootstrapTfstateResourceStatus.StorageAccountStatus)"
    Write-Host "Tfstate container status: $($bootstrapTfstateResourceStatus.ContainerStatus)"
    Write-Host "Tfstate storage role status: $($bootstrapTfstateResourceStatus.StorageRoleStatus)"
    Write-Host "GitHub envs created: $(@($createdGitHubEnvironments).Count)"
    Write-Host "GitHub App ID:    $githubAppId"
    Write-Host "GitHub App slug:  $githubAppSlug"
    Write-Host "GitHub App install: $githubAppInstallationId"
    Write-Host "OIDC subjects ensured: $(@($federatedCredentialSubjects).Count)"
Write-Host ""
Write-Host "Next steps:"
if ($SkipBootstrapDispatch) {
    Write-Host "1. Run workflow 000 to create the workload RG, provision the tfstate backend in its own RG, and import the workload RG into Terraform state using the TFSTATE_* values."
    Write-Host "2. Run workflow 100 to validate secrets, variables, OIDC, and Azure access."
    Write-Host "3. Run workflow 200, then workflow 210 for the first deployment."
} else {
    Write-Host "1. Monitor workflow 000 and confirm the bootstrap completes successfully."
    Write-Host "2. Run workflow 100 to validate secrets, variables, OIDC, and Azure access."
    Write-Host "3. Run workflow 200, then workflow 210 for the first deployment."
}
