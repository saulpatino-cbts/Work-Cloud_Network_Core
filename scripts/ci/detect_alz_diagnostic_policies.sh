#!/usr/bin/env bash
# Detects whether an Azure Landing Zone (ALZ) governance policy already manages
# diagnostic settings on the target subscription via a DeployIfNotExists (DINE)
# effect. ALZ deployments assign a "Deploy diagnostic settings" initiative
# (commonly named Deploy-Diag-Logs) at a management-group scope ABOVE the
# subscription. That policy auto-creates a "setByPolicy-*" diagnostic setting on
# every supported resource the instant it is created, and races any
# Terraform-managed diagnostic setting on the same resource — which the azurerm
# provider surfaces as a false "already exists / needs import" error mid-apply.
#
# Rather than fight org-owned governance (which is not ours to remove on a
# customer ALZ), we DETECT it and tell Terraform to stand down: this writes
# `manage_diagnostic_settings=false` to GITHUB_OUTPUT so the deploy workflow can
# export TF_VAR_manage_diagnostic_settings=false. Logs still flow — to the
# centrally governed workspace the policy targets.
#
# Detection is non-fatal and fail-safe: any error, or no policy found, defaults
# to manage_diagnostic_settings=true (Terraform manages diagnostics), preserving
# behaviour on non-ALZ subscriptions.
#
# IMPORTANT: ALZ diagnostics policies are assigned at MANAGEMENT GROUP scope, not
# the subscription. `az policy assignment list --scope <sub>` does NOT return
# inherited MG assignments, so we walk the subscription's MG ancestor chain.
#
# Required env:
#   AZURE_SUBSCRIPTION_ID  — target subscription (defaults to current az context)
# Optional env:
#   GITHUB_OUTPUT          — when set, the decision is written here
#   GITHUB_STEP_SUMMARY    — when set, a human-readable note is appended here
set -euo pipefail

# Disable MSYS path mangling so /subscriptions/... and /providers/... scopes
# survive intact when this ever runs under Git Bash on Windows.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv 2>/dev/null || echo "")}"

emit_decision() {
  local value="$1"
  [[ -n "${GITHUB_OUTPUT:-}" ]] && echo "manage_diagnostic_settings=${value}" >> "$GITHUB_OUTPUT"
  echo "Decision: manage_diagnostic_settings=${value}"
}

if [[ -z "$SUBSCRIPTION_ID" ]]; then
  echo "::warning::Could not resolve subscription; defaulting to manage_diagnostic_settings=true"
  emit_decision "true"
  exit 0
fi

echo "Scanning policy assignments governing subscription ${SUBSCRIPTION_ID} for ALZ diagnostic-settings (DeployIfNotExists)..."

# Build the list of scopes to check: the subscription itself, plus every
# management-group ancestor up to the tenant root.
SCOPES=("/subscriptions/${SUBSCRIPTION_ID}")

# Find the immediate parent MG of the subscription, then walk upward.
# managementGroups/{mg}?$expand=ancestors returns the full ancestor chain.
PARENT_MG="$(az rest --method get \
  --url "https://management.azure.com/providers/Microsoft.Management/managementGroups?api-version=2020-05-01&\$filter=children/any(c: c/name eq '${SUBSCRIPTION_ID}')" \
  --query "value[0].name" -o tsv 2>/dev/null || echo "")"

# Fallback: derive parent via the subscription's own management-group membership.
if [[ -z "$PARENT_MG" ]]; then
  PARENT_MG="$(az rest --method get \
    --url "https://management.azure.com/providers/Microsoft.Management/managementGroups/?api-version=2020-05-01" \
    --query "value[].name" -o tsv 2>/dev/null | while read -r mg; do
      if az rest --method get \
        --url "https://management.azure.com/providers/Microsoft.Management/managementGroups/${mg}/descendants?api-version=2020-05-01" \
        --query "value[?name=='${SUBSCRIPTION_ID}'] | [0].name" -o tsv 2>/dev/null | grep -q "${SUBSCRIPTION_ID}"; then
        echo "$mg"; break
      fi
    done || echo "")"
fi

# Walk the ancestor chain via the ancestors expansion on the parent MG.
if [[ -n "$PARENT_MG" ]]; then
  ANCESTORS="$(az rest --method get \
    --url "https://management.azure.com/providers/Microsoft.Management/managementGroups/${PARENT_MG}?api-version=2020-05-01&\$expand=ancestors" \
    --query "[properties.details.parent.name, properties.name] | []" -o tsv 2>/dev/null || echo "")"
  # Always include the direct parent, then any ancestors we can resolve.
  for mg in "$PARENT_MG" $ANCESTORS; do
    [[ -n "$mg" ]] && SCOPES+=("/providers/Microsoft.Management/managementGroups/${mg}")
  done
fi

# As a comprehensive backstop, also scan every MG the runner identity can see.
# On an ALZ the diagnostics initiative lives on a platform/intermediate MG, so a
# breadth scan guarantees we find it even if ancestor resolution is incomplete.
while read -r mg; do
  [[ -n "$mg" ]] && SCOPES+=("/providers/Microsoft.Management/managementGroups/${mg}")
done < <(az account management-group list --query "[].name" -o tsv 2>/dev/null || true)

# De-duplicate scopes.
readarray -t SCOPES < <(printf '%s\n' "${SCOPES[@]}" | awk '!seen[$0]++')

# An ALZ diagnostics assignment is recognised by the assignment name or its
# policy definition id matching the well-known "Deploy-Diag" / diagnostic-logs
# pattern. We match on the assignment NAME (fast, no per-definition lookups),
# which on ALZ is consistently "Deploy-Diag-Logs" (and variants).
DIAG_NAME_PATTERN='[Dd]eploy.*[Dd]iag|[Dd]iagnostic.*[Ll]og|setByPolicy'

DETECTED="false"
DETECTED_WHERE=""
DETECTED_NAME=""

for scope in "${SCOPES[@]}"; do
  # Pull assignment name + definition id pairs at this scope.
  MATCH="$(az policy assignment list --scope "$scope" \
    --query "[].{n:name, d:policyDefinitionId, dn:displayName}" -o tsv 2>/dev/null \
    | grep -iE "$DIAG_NAME_PATTERN" | head -1 || true)"
  if [[ -n "$MATCH" ]]; then
    DETECTED="true"
    DETECTED_WHERE="$scope"
    DETECTED_NAME="$(echo "$MATCH" | cut -f1)"
    break
  fi
done

# Detection is INFORMATIONAL by default. We dual-ship: our uniquely-named
# settings coexist with the policy's "setByPolicy-*" settings (Azure allows up
# to 5 per resource), and a stabilization delay in the Terraform module avoids
# the create-race. So the decision stays `true` (Terraform manages its own
# settings) even when a policy is detected — we just surface what's happening.
#
# An operator can still force a full stand-down by setting the repo/environment
# variable ALZ_DIAGNOSTICS_STANDDOWN=true, in which case we emit `false` and the
# module skips its settings entirely (policy-only diagnostics).
STANDDOWN="${ALZ_DIAGNOSTICS_STANDDOWN:-false}"

if [[ "$DETECTED" == "true" ]]; then
  if [[ "$STANDDOWN" == "true" ]]; then
    echo "::warning::ALZ diagnostic-settings policy '${DETECTED_NAME}' detected at ${DETECTED_WHERE}; ALZ_DIAGNOSTICS_STANDDOWN=true -> Terraform diagnostic settings DISABLED (policy-only diagnostics)."
    DECISION="false"
    TF_STATE="disabled (stand-down requested)"
  else
    echo "::warning::ALZ diagnostic-settings policy '${DETECTED_NAME}' detected at ${DETECTED_WHERE}. Terraform dual-ships its own uniquely-named settings alongside the policy's 'setByPolicy-*' settings (a stabilization delay avoids the azurerm create-race). Set ALZ_DIAGNOSTICS_STANDDOWN=true to disable Terraform settings entirely."
    DECISION="true"
    TF_STATE="enabled (dual-ship with policy)"
  fi
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
      echo "## Diagnostic settings governance"
      echo ""
      echo "⚠️ An **Azure Landing Zone DeployIfNotExists policy** governs diagnostic settings for this subscription."
      echo ""
      echo "| | |"
      echo "|---|---|"
      echo "| Terraform-managed diagnostics | **${TF_STATE}** |"
      echo "| Detected assignment | \`${DETECTED_NAME}\` |"
      echo "| Scope | \`${DETECTED_WHERE}\` |"
      echo "| Behaviour | Our settings are uniquely named and created after a stabilization delay, so they coexist with the policy's \`setByPolicy-*\` settings (Azure allows 5 per resource). |"
      echo "| Override | Set \`ALZ_DIAGNOSTICS_STANDDOWN=true\` to disable Terraform settings entirely. |"
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  emit_decision "$DECISION"
else
  echo "No ALZ diagnostic-settings policy detected across ${#SCOPES[@]} scope(s). Terraform manages diagnostic settings normally."
  emit_decision "true"
fi
