#!/usr/bin/env bash
# Validates Foundry private DNS resolution and managed identity inference by
# running a Container Apps Job inside the VNet. No exec transport required —
# works correctly with scale-to-zero and eliminates all min-replicas churn.
set -euo pipefail

: "${RESOURCE_GROUP_NAME:?RESOURCE_GROUP_NAME is required}"
: "${CONTAINER_APP_ENVIRONMENT_ID:?CONTAINER_APP_ENVIRONMENT_ID is required}"
: "${WEB_CONTAINER_APP_NAME:?WEB_CONTAINER_APP_NAME is required}"
: "${PRIVATE_ENDPOINT_SUBNET_PREFIX:?PRIVATE_ENDPOINT_SUBNET_PREFIX is required}"
: "${MANAGED_IDENTITY_CLIENT_ID:?MANAGED_IDENTITY_CLIENT_ID is required}"
: "${DOCKERHUB_USERNAME:?DOCKERHUB_USERNAME is required}"
: "${DOCKERHUB_PASSWORD:?DOCKERHUB_PASSWORD is required}"
: "${RUN_ID:?RUN_ID is required}"

RG="$RESOURCE_GROUP_NAME"
CAE="${CONTAINER_APP_ENVIRONMENT_ID##*/}"
JOB="job-validate-foundry-${RUN_ID}"

# Resolve UAI resource ID from client ID.
UAI_ID=$(az identity list --resource-group "$RG" \
  --query "[?clientId=='${MANAGED_IDENTITY_CLIENT_ID}'].id | [0]" -o tsv 2>/dev/null || echo "")
if [[ -z "$UAI_ID" ]]; then
  echo "::error::Could not find user-assigned managed identity with clientId=$MANAGED_IDENTITY_CLIENT_ID in $RG"
  exit 1
fi

# Read Foundry endpoint and model from the deployed web Container App.
WEB_IMAGE=$(az containerapp show --name "$WEB_CONTAINER_APP_NAME" --resource-group "$RG" \
  --query "properties.template.containers[0].image" -o tsv)
FOUNDRY_ENDPOINT=$(az containerapp show --name "$WEB_CONTAINER_APP_NAME" --resource-group "$RG" \
  --query "properties.template.containers[0].env[?name=='FOUNDRY_CLAUDE_ENDPOINT'].value | [0]" -o tsv 2>/dev/null || echo "")
FOUNDRY_MODEL=$(az containerapp show --name "$WEB_CONTAINER_APP_NAME" --resource-group "$RG" \
  --query "properties.template.containers[0].env[?name=='FOUNDRY_CLAUDE_MODEL'].value | [0]" -o tsv 2>/dev/null || echo "claude-sonnet-4-6")

if [[ -z "$FOUNDRY_ENDPOINT" ]]; then
  echo "::error::FOUNDRY_CLAUDE_ENDPOINT is not set on $WEB_CONTAINER_APP_NAME — cannot validate Foundry access."
  exit 1
fi

echo "Validation job: $JOB"
echo "  Image:            $WEB_IMAGE"
echo "  Foundry endpoint: $FOUNDRY_ENDPOINT"
echo "  Private subnet:   $PRIVATE_ENDPOINT_SUBNET_PREFIX"
echo "  UAI client_id:    $MANAGED_IDENTITY_CLIENT_ID"

# The Node.js validation script. AZURE_CLIENT_ID env var is set in the job
# container so DefaultAzureCredential uses the user-assigned managed identity.
read -r -d '' NODE_SCRIPT <<'NODE' || true
const dns = require("node:dns").promises;
const { URL } = require("node:url");
const { DefaultAzureCredential } = require("@azure/identity");

function ipToInt(ip) {
  const parts = ip.split(".").map(Number);
  if (parts.length !== 4 || parts.some(p => !Number.isInteger(p) || p < 0 || p > 255))
    throw new Error(`Unsupported IPv4 address: ${ip}`);
  return parts.reduce((acc, p) => ((acc << 8) + p) >>> 0, 0);
}

function inCidr(ip, cidr) {
  const [network, prefixText] = cidr.split("/");
  const prefix = Number(prefixText);
  if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32)
    throw new Error(`Invalid CIDR prefix: ${cidr}`);
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return (ipToInt(ip) & mask) === (ipToInt(network) & mask);
}

async function main() {
  const endpoint = process.env.FOUNDRY_CLAUDE_ENDPOINT;
  const model = process.env.FOUNDRY_CLAUDE_MODEL || "claude-sonnet-4-6";
  const privateEndpointSubnetPrefix = process.env.PRIVATE_ENDPOINT_SUBNET_PREFIX;

  if (!endpoint) throw new Error("FOUNDRY_CLAUDE_ENDPOINT is not configured.");
  if (!privateEndpointSubnetPrefix) throw new Error("PRIVATE_ENDPOINT_SUBNET_PREFIX was not supplied.");

  const host = new URL(endpoint).hostname;
  const dnsResults = await dns.lookup(host, { all: true, verbatim: true });
  const privateMatches = dnsResults.filter(r => r.family === 4 && inCidr(r.address, privateEndpointSubnetPrefix));

  if (privateMatches.length === 0) {
    throw new Error(
      `Foundry host ${host} did not resolve into ${privateEndpointSubnetPrefix}. ` +
      `Resolved: ${dnsResults.map(r => r.address).join(", ")}`
    );
  }

  // AZURE_CLIENT_ID env var tells DefaultAzureCredential which UAI to use.
  const credential = new DefaultAzureCredential();
  const token = await credential.getToken("https://cognitiveservices.azure.com/.default");
  if (!token?.token) throw new Error("Managed identity did not return a Cognitive Services token.");

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "anthropic-version": "2023-06-01",
      Authorization: `Bearer ${token.token}`,
    },
    body: JSON.stringify({
      model,
      max_tokens: 16,
      messages: [{ role: "user", content: "Reply with OK." }],
    }),
  });

  const body = await response.text();
  if (!response.ok)
    throw new Error(`Foundry inference failed with HTTP ${response.status}: ${body.slice(0, 500)}`);

  console.log(JSON.stringify({
    status: "passed",
    host,
    resolved_addresses: dnsResults.map(r => r.address),
    private_endpoint_subnet_prefix: privateEndpointSubnetPrefix,
    inference_http_status: response.status,
  }, null, 2));
}

main().catch(err => { console.error(err.stack || err.message || String(err)); process.exit(1); });
NODE

NODE_SCRIPT_B64="$(printf '%s' "$NODE_SCRIPT" | base64 -w 0)"

# Log Analytics workspace ID for log capture (best-effort).
LAW_ID=$(az monitor log-analytics workspace list -g "$RG" --query '[0].customerId' -o tsv 2>/dev/null || echo "")

cleanup() {
  az containerapp job delete --name "$JOB" --resource-group "$RG" --yes 2>/dev/null || true
}
trap cleanup EXIT

echo "Creating validation job $JOB..."
az containerapp job create \
  --name "$JOB" \
  --resource-group "$RG" \
  --environment "$CAE" \
  --trigger-type Manual \
  --replica-timeout 120 \
  --replica-retry-limit 0 \
  --replica-completion-count 1 \
  --parallelism 1 \
  --image "$WEB_IMAGE" \
  --mi-user-assigned "$UAI_ID" \
  --command "/bin/sh" \
  --args="-c" 'echo "$VALIDATION_SCRIPT_B64" | base64 -d | node' \
  --env-vars \
    "VALIDATION_SCRIPT_B64=${NODE_SCRIPT_B64}" \
    "AZURE_CLIENT_ID=${MANAGED_IDENTITY_CLIENT_ID}" \
    "FOUNDRY_CLAUDE_ENDPOINT=${FOUNDRY_ENDPOINT}" \
    "FOUNDRY_CLAUDE_MODEL=${FOUNDRY_MODEL:-claude-sonnet-4-6}" \
    "PRIVATE_ENDPOINT_SUBNET_PREFIX=${PRIVATE_ENDPOINT_SUBNET_PREFIX}" \
  --registry-server "docker.io" \
  --registry-username "$DOCKERHUB_USERNAME" \
  --registry-password "$DOCKERHUB_PASSWORD"

echo "Starting validation job..."
az containerapp job start --name "$JOB" --resource-group "$RG"

echo "Polling for completion (up to 3 minutes)..."
VALIDATION_STATUS="Running"
for i in $(seq 1 18); do
  EXEC_JSON=$(az containerapp job execution list --name "$JOB" --resource-group "$RG" \
    --query "[-1]" -o json 2>/dev/null || echo "{}")
  STATUS=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('properties',{}).get('status','Running'))" <<< "$EXEC_JSON" 2>/dev/null || echo "Running")
  EXEC_NAME=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name',''))" <<< "$EXEC_JSON" 2>/dev/null || echo "")
  VALIDATION_STATUS="$STATUS"
  echo "  [$i/18] Status: $STATUS"

  case "$STATUS" in
    Succeeded)
      echo "Foundry private access validation passed."
      if [[ -n "$LAW_ID" && -n "$EXEC_NAME" ]]; then
        az monitor log-analytics query -w "$LAW_ID" \
          --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(5m) | where ContainerAppName_s == '${JOB}' | order by TimeGenerated asc | project TimeGenerated, Log_s" \
          -o table 2>/dev/null || true
      fi
      exit 0
      ;;
    Failed|Stopped)
      echo "::error::Foundry validation job failed. Capturing logs..."
      if [[ -n "$LAW_ID" ]]; then
        az monitor log-analytics query -w "$LAW_ID" \
          --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(5m) | where ContainerAppName_s == '${JOB}' | order by TimeGenerated asc | project TimeGenerated, Log_s" \
          -o table 2>/dev/null || echo "log-query-unavailable"
      fi
      exit 1
      ;;
  esac
  [[ $i -lt 18 ]] && sleep 10
done

echo "::error::Foundry validation job timed out after 3 minutes."
if [[ -n "$LAW_ID" ]]; then
  az monitor log-analytics query -w "$LAW_ID" \
    --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(5m) | where ContainerAppName_s == '${JOB}' | order by TimeGenerated asc | project TimeGenerated, Log_s" \
    -o table 2>/dev/null || echo "log-query-unavailable"
fi
exit 1
