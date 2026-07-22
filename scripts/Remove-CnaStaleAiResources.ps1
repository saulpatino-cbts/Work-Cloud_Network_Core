[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet("dev", "prod")]
    [string]$Environment = "dev",

    [string]$RegionShort,

    [ValidateSet("StaleAi", "Environment", "AllCna")]
    [string]$Scope = "Environment",

    [string]$SubscriptionId,

    [switch]$IncludeTfState,

    [switch]$Delete
)

$ErrorActionPreference = "Stop"

function Invoke-AzJson {
    param([string[]]$Arguments)

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & az @Arguments --only-show-errors -o json 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference

    if ($exitCode -ne 0 -or [string]::IsNullOrWhiteSpace($output)) { return $null }
    return $output | ConvertFrom-Json
}

function Remove-IfRequested {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [string]$Label,
        [scriptblock]$DeleteAction
    )

    if ($Delete -and $PSCmdlet.ShouldProcess($Label, 'delete')) {
        & $DeleteAction
    }
}

function ConvertTo-FlatArray {
    param($Value)

    $items = [System.Collections.Generic.List[object]]::new()
    foreach ($item in @($Value)) {
        if ($null -eq $item) { continue }

        if ($item -is [System.Array]) {
            foreach ($nested in $item) {
                if ($null -ne $nested) {
                    $items.Add($nested)
                }
            }
            continue
        }

        $items.Add($item)
    }

    return $items.ToArray()
}

function Add-ResourceRows {
    param(
        [System.Collections.Generic.List[object]]$Rows,
        [string]$ResourceGroup
    )

    $resources = ConvertTo-FlatArray (Invoke-AzJson @("resource", "list", "--resource-group", $ResourceGroup))
    foreach ($resource in $resources) {
        $Rows.Add([pscustomobject]@{
            Scope         = "Resource"
            ResourceGroup = $ResourceGroup
            Name          = $resource.name
            Type          = $resource.type
            Location      = $resource.location
            Id            = $resource.id
        })
    }
}

function Add-GroupName {
    param(
        [System.Collections.Generic.List[string]]$Groups,
        [string]$Name
    )

    if ([string]::IsNullOrWhiteSpace($Name)) { return }
    if (-not ($Groups.Contains($Name))) {
        $Groups.Add($Name)
    }
}

if ($SubscriptionId) {
    az account set --subscription $SubscriptionId | Out-Null
}

$account = Invoke-AzJson @("account", "show")
if (-not $account) {
    throw "Azure CLI is not logged in. Run az login first."
}

$RegionShort = $RegionShort.Trim()
if ([string]::IsNullOrWhiteSpace($RegionShort)) {
    throw "RegionShort is required. Pass -RegionShort or set AZURE_REGION_SHORT in the calling workflow."
}

$namePrefix = "cna-$Environment-$RegionShort"
$workloadRg = "rg-$namePrefix"
$tfstateRg = "${workloadRg}-tfstate"
$managedRgPatterns = @(
    "ai_*$($namePrefix)*_*_managed",
    "rg-$($namePrefix)-cae-managed",
    "ME_*_rg-$($namePrefix)_*"
)

$staleOpenAiAccount = "aoaicna$Environment$RegionShort"
$staleOpenAiPe = "pe-$namePrefix-openai"
$staleOpenAiZone = "privatelink.openai.azure.com"
$staleOpenAiDnsLink = "pdns-link-$namePrefix-openai"
$keyVault = "$namePrefix-kv"
$keyVaultSecret = "cna-azure-openai-endpoint"

$allGroups = ConvertTo-FlatArray (Invoke-AzJson @("group", "list"))
$groupNames = [System.Collections.Generic.List[string]]::new()

switch ($Scope) {
    "StaleAi" {
        Add-GroupName -Groups $groupNames -Name $workloadRg
    }
    "Environment" {
        Add-GroupName -Groups $groupNames -Name $workloadRg
        foreach ($pattern in $managedRgPatterns) {
            foreach ($match in @($allGroups | Where-Object { $_.name -like $pattern })) {
                Add-GroupName -Groups $groupNames -Name ([string]$match.name)
            }
        }
    }
    "AllCna" {
        foreach ($match in @($allGroups | Where-Object {
            $_.name -eq $workloadRg -or
            $_.name -eq $tfstateRg -or
            $_.name -like "ai_*cna-$Environment-*_*_managed" -or
            $_.name -like "rg-cna-$Environment-*-cae-managed" -or
            $_.name -like "ME_*_rg-$($namePrefix)_*"
        })) {
            Add-GroupName -Groups $groupNames -Name ([string]$match.name)
        }
        if ($IncludeTfState) {
            Add-GroupName -Groups $groupNames -Name $tfstateRg
        }
    }
}

$groups = @($groupNames.ToArray() | Sort-Object -Unique)
if (-not $IncludeTfState) {
    $groups = @($groups | Where-Object { $_ -ne $tfstateRg })
}
$rows = [System.Collections.Generic.List[object]]::new()

Write-Host "Subscription: $($account.name) ($($account.id))"
Write-Host "Environment:  $Environment"
Write-Host "RegionShort:  $RegionShort"
Write-Host "Scope:        $Scope"
Write-Host "Mode:         $(if ($Delete) { 'DELETE' } else { 'LIST ONLY' })"
Write-Host ""

foreach ($groupName in $groups) {
    $group = $allGroups | Where-Object { $_.name -eq $groupName } | Select-Object -First 1
    if (-not $group) { continue }

    if ($Scope -ne "StaleAi") {
        $rows.Add([pscustomobject]@{
            Scope         = "ResourceGroup"
            ResourceGroup = $group.name
            Name          = $group.name
            Type          = "Microsoft.Resources/resourceGroups"
            Location      = $group.location
            Id            = "/subscriptions/$($account.id)/resourceGroups/$($group.name)"
        })
    }

    if ($Scope -eq "StaleAi") {
        $resources = ConvertTo-FlatArray (Invoke-AzJson @("resource", "list", "--resource-group", $groupName))
        foreach ($resource in $resources | Where-Object {
            $_.name -eq $staleOpenAiAccount -or
            $_.name -eq "adms-mnvji9i5-eastus2" -or
            $_.name -eq $staleOpenAiPe -or
            $_.name -like "$staleOpenAiPe.nic.*" -or
            $_.name -eq $staleOpenAiZone -or
            $_.name -like "$staleOpenAiZone/$staleOpenAiDnsLink"
        }) {
            $rows.Add([pscustomobject]@{
                Scope         = "Resource"
                ResourceGroup = $groupName
                Name          = $resource.name
                Type          = $resource.type
                Location      = $resource.location
                Id            = $resource.id
            })
        }

        $openAi = Invoke-AzJson @("cognitiveservices", "account", "show", "--name", $staleOpenAiAccount, "--resource-group", $workloadRg)
        if ($openAi) {
            $assignments = ConvertTo-FlatArray (Invoke-AzJson @("role", "assignment", "list", "--scope", $openAi.id, "--role", "Cognitive Services OpenAI User"))
            foreach ($assignment in $assignments) {
                $rows.Add([pscustomobject]@{
                    Scope         = "RoleAssignment"
                    ResourceGroup = $workloadRg
                    Name          = $assignment.name
                    Type          = "Microsoft.Authorization/roleAssignments"
                    Location      = "global"
                    Id            = $assignment.id
                })
            }
        }
    } else {
        Add-ResourceRows -Rows $rows -ResourceGroup $groupName
    }
}

if ($Scope -eq "StaleAi") {
    $secret = Invoke-AzJson @("keyvault", "secret", "show", "--vault-name", $keyVault, "--name", $keyVaultSecret)
    if ($secret) {
        $rows.Add([pscustomobject]@{
            Scope         = "KeyVaultSecret"
            ResourceGroup = $keyVault
            Name          = $keyVaultSecret
            Type          = "Microsoft.KeyVault/vaults/secrets"
            Location      = "global"
            Id            = $secret.id
        })
    }
}

if ($rows.Count -eq 0) {
    Write-Host "No matching CNA resources found."
    exit 0
}

$rows | Sort-Object Scope, ResourceGroup, Type, Name | Format-Table Scope, ResourceGroup, Name, Type, Location -AutoSize

if (-not $Delete) {
    Write-Host ""
    if ($Scope -eq "StaleAi") {
        Write-Host "List-only mode. Add -Delete to remove only the listed stale AI artifacts."
    } else {
        Write-Host "List-only mode. Add -Delete to remove the listed resource groups and their child resources."
    }
    exit 0
}

if ($Scope -eq "StaleAi") {
    Remove-IfRequested "Key Vault secret $keyVault/$keyVaultSecret" {
        az keyvault secret delete --vault-name $keyVault --name $keyVaultSecret --only-show-errors | Out-Null
    }

    $openAi = Invoke-AzJson @("cognitiveservices", "account", "show", "--name", $staleOpenAiAccount, "--resource-group", $workloadRg)
    if ($openAi) {
        $assignments = ConvertTo-FlatArray (Invoke-AzJson @("role", "assignment", "list", "--scope", $openAi.id, "--role", "Cognitive Services OpenAI User"))
        foreach ($assignment in $assignments) {
            Remove-IfRequested "Role assignment $($assignment.name)" {
                az role assignment delete --ids $assignment.id --only-show-errors | Out-Null
            }
        }
    }

    Remove-IfRequested "Private endpoint $workloadRg/$staleOpenAiPe" {
        az network private-endpoint delete --name $staleOpenAiPe --resource-group $workloadRg --only-show-errors | Out-Null
    }

    Remove-IfRequested "Private DNS VNet link $workloadRg/$staleOpenAiZone/$staleOpenAiDnsLink" {
        az network private-dns link vnet delete --name $staleOpenAiDnsLink --zone-name $staleOpenAiZone --resource-group $workloadRg --yes --only-show-errors | Out-Null
    }

    Remove-IfRequested "Private DNS zone $workloadRg/$staleOpenAiZone" {
        az network private-dns zone delete --name $staleOpenAiZone --resource-group $workloadRg --yes --only-show-errors | Out-Null
    }

    Remove-IfRequested "Azure OpenAI account $workloadRg/$staleOpenAiAccount" {
        az cognitiveservices account delete --name $staleOpenAiAccount --resource-group $workloadRg --only-show-errors | Out-Null
    }

    Remove-IfRequested "Portal-created Foundry account $workloadRg/adms-mnvji9i5-eastus2" {
        az cognitiveservices account delete --name "adms-mnvji9i5-eastus2" --resource-group $workloadRg --only-show-errors | Out-Null
    }
} else {
    foreach ($groupName in $groups) {
        if ($groupName -eq $tfstateRg -and -not $IncludeTfState) { continue }

        Remove-IfRequested "Resource group $groupName" {
            az group delete --name $groupName --yes --no-wait --only-show-errors | Out-Null
        }
    }
}

Write-Host "Cleanup command sequence submitted. Resource group deletes run asynchronously; rerun in list-only mode to verify."
