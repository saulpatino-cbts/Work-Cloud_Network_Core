[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$AppId,

    [Parameter(Mandatory = $true)]
    [string]$ApplicationUrl
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($ApplicationUrl -notmatch '^https://') {
    throw "ApplicationUrl must be an https URL."
}

$normalizedUrl = $ApplicationUrl.TrimEnd('/')
$redirectUri = "$normalizedUrl/api/auth/callback/microsoft-entra-id"

$appJson = & az ad app show --id $AppId --output json
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($appJson)) {
    throw "Failed to read Entra application '$AppId'."
}

$app = $appJson | ConvertFrom-Json
$web = if ($app.web) { $app.web } else { @{} }
$redirectUris = @($web.redirectUris)

if (-not ($redirectUris -contains $redirectUri)) {
    $redirectUris = @($redirectUris + $redirectUri)
}

$currentHomePage = [string]$web.homePageUrl
$needsHomePageUpdate = $currentHomePage -ne $normalizedUrl
$needsRedirectUpdate = -not (($web.redirectUris | ForEach-Object { [string]$_ }) -contains $redirectUri)

if (-not $needsHomePageUpdate -and -not $needsRedirectUpdate) {
    Write-Host "Entra app already matches application URL $normalizedUrl"
    return
}

$updateArgs = @(
    "ad", "app", "update",
    "--id", $AppId,
    "--web-home-page-url", $normalizedUrl,
    "--web-redirect-uris"
)
$updateArgs += $redirectUris

if ($PSCmdlet.ShouldProcess($AppId, "sync Entra web homepage and redirect URIs")) {
    & az @updateArgs --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update Entra application '$AppId'."
    }
}

Write-Host "Synced Entra application:"
Write-Host "  Home page URL : $normalizedUrl"
Write-Host "  Redirect URI  : $redirectUri"
