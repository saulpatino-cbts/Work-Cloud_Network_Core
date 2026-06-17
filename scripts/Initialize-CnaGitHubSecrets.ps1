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

    if ($CurrentAccount -and $CurrentAccount.id) {
        $selected = $accounts | Where-Object { $_.id -eq $CurrentAccount.id } | Select-Object -First 1
        if ($selected) {
            Write-Ok "Using current Azure subscription: $($selected.name) ($($selected.id))"
            return $selected
        }
    }

    if ($accounts.Count -eq 1) {
        $selected = $accounts[0]
        Write-Ok "Using the only available subscription: $($selected.name) ($($selected.id))"
        return $selected
    }

    if (-not $ForceInteractive) {
        $selected = $accounts | Where-Object { $_.isDefault -eq $true } | Select-Object -First 1
        if (-not $selected) {
            $selected = $accounts[0]
        }
        Write-Warn "Multiple Azure subscriptions are available. Using $($selected.name) ($($selected.id)). Pass -SubscriptionId or -ForceInteractive to override."
        return $selected
    }

    Write-Host "Available Azure subscriptions:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $accounts.Count; $i++) {
        $a = $accounts[$i]
        Write-Host "  [$i] $($a.name) ($($a.id))  tenant=$($a.tenantId)"
    }

    while ($true) {
        $choice = Read-Host "Select a subscription by number, or type the subscription ID/name (default: $($CurrentAccount.name) / $($CurrentAccount.id))"
        if ([string]::IsNullOrWhiteSpace($choice)) {
            $choice = $CurrentAccount.id
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
    } else {
        Write-Ok "$PurposeLabel resource group exists: $ResourceGroupName"
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
    Ensure-ResourceGroup -SubscriptionId $SubscriptionId -Location $Location -ResourceGroupName $ResourceGroupName -PurposeLabel "tfstate"

    $storageId = & az storage account show --name $StorageAccountName --resource-group $ResourceGroupName --subscription $SubscriptionId --query id -o tsv 2>$null
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
    if ($LASTEXITCODE -ne 0) {
        if ($PSCmdlet.ShouldProcess($ContainerName, "create tfstate blob container")) {
            & az storage container create --name $ContainerName --account-name $StorageAccountName --account-key $accountKey --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create tfstate blob container '$ContainerName'." }
        }
        Write-Ok "Created tfstate blob container: $ContainerName"
    } else {
        Write-Ok "Tfstate blob container exists: $ContainerName"
    }

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
        } else {
            Write-Ok "CI identity already has Storage Blob Data Contributor on tfstate storage"
        }
    } else {
        Write-Warn "Could not resolve service principal object ID for $ClientId. Workflow 000 may need to assign storage RBAC itself."
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

$tenantId = ""
$resolvedSubscriptionId = ""
$resolvedSubscriptionName = ""
$appId = ""
$entraClientSecret = $null

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
        Write-Host "    [INFO] CNA_NEXTAUTH_URL is 'none'. Redirect URI will be added later after workflow 031 exposes the real Front Door hostname."
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

$secretValues = [ordered]@{
    AZURE_CLIENT_ID                = $appId
    AZURE_TENANT_ID                = $tenantId
    AZURE_SUBSCRIPTION_ID          = $resolvedSubscriptionId
    CNA_ENTRA_CLIENT_SECRET        = $entraClientSecret
    CNA_POSTGRES_ADMIN_PASSWORD    = Read-SecretValue -Name "CNA_POSTGRES_ADMIN_PASSWORD" -Description "PostgreSQL admin password" -Exists $existingSecrets.ContainsKey("CNA_POSTGRES_ADMIN_PASSWORD") -GenerateBytes 18 -Required
    CNA_NEXTAUTH_SECRET            = Read-SecretValue -Name "CNA_NEXTAUTH_SECRET" -Description "Auth.js signing secret" -Exists $existingSecrets.ContainsKey("CNA_NEXTAUTH_SECRET") -GenerateBytes 32 -Required
    CNA_CREDENTIAL_ENCRYPTION_KEY  = Read-SecretValue -Name "CNA_CREDENTIAL_ENCRYPTION_KEY" -Description "base64 32-byte AES key for stored cloud credentials" -Exists $existingSecrets.ContainsKey("CNA_CREDENTIAL_ENCRYPTION_KEY") -GenerateBytes 32 -Required
    GHCR_PAT                       = Read-SecretValue -Name "GHCR_PAT" -Description "GitHub PAT with read:packages for Container Apps image pulls" -Exists $existingSecrets.ContainsKey("GHCR_PAT") -Required
    GH_VARIABLES_PAT               = Read-SecretValue -Name "GH_VARIABLES_PAT" -Description "optional PAT that lets workflow 031 update repo variables" -Exists $existingSecrets.ContainsKey("GH_VARIABLES_PAT")
    FRONTDOOR_CERTIFICATE_PFX_PASSWORD = Read-SecretValue -Name "FRONTDOOR_CERTIFICATE_PFX_PASSWORD" -Description "optional custom TLS certificate PFX password" -Exists $existingSecrets.ContainsKey("FRONTDOOR_CERTIFICATE_PFX_PASSWORD")
    CNA_AWS_ROLE_ARN               = Read-SecretValue -Name "CNA_AWS_ROLE_ARN" -Description "optional AWS OIDC role ARN for portal publishing" -Exists $existingSecrets.ContainsKey("CNA_AWS_ROLE_ARN")
    CNA_PUBLISH_BUCKET             = Read-SecretValue -Name "CNA_PUBLISH_BUCKET" -Description "optional S3 bucket for portal publishing" -Exists $existingSecrets.ContainsKey("CNA_PUBLISH_BUCKET")
}

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
    Ensure-ResourceGroup `
        -SubscriptionId $resolvedSubscriptionId `
        -Location $BootstrapLocation `
        -ResourceGroupName $bootstrapWorkloadResourceGroup `
        -PurposeLabel "workload"

    Ensure-TfstateBackendResources `
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

Write-Step "Summary"
Write-Host "Repository:       $Repo"
Write-Host "Branch:           $Branch"
Write-Host "Environment:      $Environment"
Write-Host "App registration: $AppDisplayName ($appId)"
Write-Host "Workload RG:      $bootstrapWorkloadResourceGroup"
Write-Host "Tfstate RG:       $bootstrapTfstateResourceGroup"
Write-Host "Secrets set:      $setSecretCount"
Write-Host "Secrets kept/skipped: $keptSecretCount"
Write-Host "Variables set:    $setVariableCount"
Write-Host ""
Write-Host "Next steps:"
if ($SkipBootstrapDispatch) {
    Write-Host "1. Run workflow 000 to create the workload RG, provision the tfstate backend in its own RG, and import the workload RG into Terraform state using the TFSTATE_* values."
    Write-Host "2. Run workflow 010 to validate secrets, variables, OIDC, and Azure access."
    Write-Host "3. Run workflow 030, then workflow 031 for the first deployment."
} else {
    Write-Host "1. Monitor workflow 000 and confirm the bootstrap completes successfully."
    Write-Host "2. Run workflow 010 to validate secrets, variables, OIDC, and Azure access."
    Write-Host "3. Run workflow 030, then workflow 031 for the first deployment."
}
