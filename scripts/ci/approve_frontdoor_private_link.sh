#!/usr/bin/env bash
set -euo pipefail

: "${MANAGED_ENV_ID:?MANAGED_ENV_ID is required}"
: "${RESOURCE_GROUP_NAME:?RESOURCE_GROUP_NAME is required}"

REQUEST_DESCRIPTION="${REQUEST_DESCRIPTION:-Azure Front Door Private Link request for CNA web origin}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SLEEP_SECONDS:-20}"
MANAGED_ENV_NAME="${MANAGED_ENV_NAME:-${MANAGED_ENV_ID##*/}}"

echo "Checking Front Door private endpoint requests for managed environment: ${MANAGED_ENV_NAME}"
echo "Expected request description: ${REQUEST_DESCRIPTION}"

matching_ids=""

for ((attempt=1; attempt<=MAX_ATTEMPTS; attempt++)); do
  connections_json="$(
    az network private-endpoint-connection list \
      --name "$MANAGED_ENV_NAME" \
      --resource-group "$RESOURCE_GROUP_NAME" \
      --type Microsoft.App/managedEnvironments \
      --output json
  )"

  matching_ids="$(
    jq -r --arg desc "$REQUEST_DESCRIPTION" '
      .[]
      | select(.properties.privateLinkServiceConnectionState.description == $desc)
      | .id
    ' <<<"$connections_json"
  )"

  if [[ -n "$matching_ids" ]]; then
    echo "Found matching private endpoint connection request(s) on attempt ${attempt}/${MAX_ATTEMPTS}."
    break
  fi

  echo "No matching private endpoint request yet (${attempt}/${MAX_ATTEMPTS}); waiting ${SLEEP_SECONDS}s..."
  sleep "$SLEEP_SECONDS"
done

if [[ -z "$matching_ids" ]]; then
  echo "::error::No Front Door private endpoint connection request matched description '${REQUEST_DESCRIPTION}'."
  exit 1
fi

approved_ids=()
while IFS= read -r connection_id; do
  [[ -z "$connection_id" ]] && continue
  status="$(
    az network private-endpoint-connection show \
      --id "$connection_id" \
      --query "properties.privateLinkServiceConnectionState.status" \
      --output tsv
  )"

  echo "Connection ${connection_id} currently reports status: ${status}"
  case "$status" in
    Approved)
      approved_ids+=("$connection_id")
      ;;
    Pending)
      az network private-endpoint-connection approve --id "$connection_id" 1>/dev/null
      approved_ids+=("$connection_id")
      echo "Approved pending connection: ${connection_id}"
      ;;
    *)
      echo "::error::Connection ${connection_id} is in unexpected state '${status}'."
      exit 1
      ;;
  esac
done <<<"$matching_ids"

for ((attempt=1; attempt<=MAX_ATTEMPTS; attempt++)); do
  pending=0
  while IFS= read -r connection_id; do
    [[ -z "$connection_id" ]] && continue
    status="$(
      az network private-endpoint-connection show \
        --id "$connection_id" \
        --query "properties.privateLinkServiceConnectionState.status" \
        --output tsv
    )"
    echo "Approval check ${attempt}/${MAX_ATTEMPTS} for ${connection_id}: ${status}"
    if [[ "$status" != "Approved" ]]; then
      pending=1
    fi
  done <<<"$(printf '%s\n' "${approved_ids[@]}")"

  if [[ "$pending" -eq 0 ]]; then
    break
  fi

  if [[ "$attempt" -lt "$MAX_ATTEMPTS" ]]; then
    sleep "$SLEEP_SECONDS"
  fi
done

for connection_id in "${approved_ids[@]}"; do
  final_status="$(
    az network private-endpoint-connection show \
      --id "$connection_id" \
      --query "properties.privateLinkServiceConnectionState.status" \
      --output tsv
  )"
  if [[ "$final_status" != "Approved" ]]; then
    echo "::error::Connection ${connection_id} did not reach Approved state. Final status: ${final_status}"
    exit 1
  fi
done

approved_ids_csv="$(IFS=,; echo "${approved_ids[*]}")"
echo "Approved Front Door private endpoint connection IDs: ${approved_ids_csv}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "approved_connection_ids=${approved_ids_csv}"
    echo "managed_environment_id=${MANAGED_ENV_ID}"
    echo "request_description=${REQUEST_DESCRIPTION}"
  } >> "$GITHUB_OUTPUT"
fi
