#!/usr/bin/env bash
set -euo pipefail

echo "scripts/setup-azure-prereqs.sh is deprecated."
echo "Use the interactive PowerShell setup instead:"
echo "  pwsh -File scripts/Initialize-CnaGitHubSecrets.ps1 -Repo owner/repo -Environment dev"
exit 1
