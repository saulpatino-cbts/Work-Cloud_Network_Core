<#
.SYNOPSIS
    Legacy wrapper for stale AI cleanup.

.DESCRIPTION
    This script is retained for backward compatibility only. The authoritative
    cleanup logic lives in scripts/cleanup-stale-ai-resources.ps1.
#>

[CmdletBinding()]
param(
    [ValidateSet("dev", "prod")]
    [string] $Environment = "dev",

    [string] $SubscriptionId,

    [switch] $DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptPath = Join-Path $PSScriptRoot "cleanup-stale-ai-resources.ps1"
$args = @(
    "-File", $scriptPath,
    "-Environment", $Environment,
    "-Scope", "StaleAi"
)

if ($SubscriptionId) {
    $args += @("-SubscriptionId", $SubscriptionId)
}

if (-not $DryRun) {
    $args += "-Delete"
}

Write-Warning "Remove-DriftedResources.ps1 is deprecated. Use scripts/cleanup-stale-ai-resources.ps1 directly."
& pwsh @args
