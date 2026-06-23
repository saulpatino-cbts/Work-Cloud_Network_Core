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

# The Node.js validation script. It depends on Node built-ins only (node:dns
# and the global fetch) — NO npm packages. The web image is a Next.js standalone
# build whose traced node_modules does not include @azure/identity, so requiring
# it crashes the container instantly. Instead the managed-identity token is
# fetched directly from the Container Apps identity REST endpoint
# (IDENTITY_ENDPOINT / IDENTITY_HEADER); AZURE_CLIENT_ID selects the UAI.
# https://learn.microsoft.com/azure/container-apps/managed-identity#rest-endpoint-reference
read -r -d '' NODE_SCRIPT <<'NODE' || true
const dns = require("node:dns").promises;
const { URL } = require("node:url");

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

// Acquire a managed-identity token from the Container Apps identity REST
// endpoint. For a user-assigned identity, client_id is required so the platform
// issues a token for the right UAI rather than a (possibly absent) system one.
async function getManagedIdentityToken(resource) {
  const identityEndpoint = process.env.IDENTITY_ENDPOINT;
  const identityHeader = process.env.IDENTITY_HEADER;
  const clientId = process.env.AZURE_CLIENT_ID;
  if (!identityEndpoint || !identityHeader)
    throw new Error("IDENTITY_ENDPOINT/IDENTITY_HEADER are not set — managed identity is not available to this container.");

  const url = new URL(identityEndpoint);
  url.searchParams.set("resource", resource);
  url.searchParams.set("api-version", "2019-08-01");
  if (clientId) url.searchParams.set("client_id", clientId);

  const res = await fetch(url, { headers: { "X-IDENTITY-HEADER": identityHeader } });
  const text = await res.text();
  if (!res.ok)
    throw new Error(`Managed identity token request failed: HTTP ${res.status}: ${text.slice(0, 500)}`);
  let parsed;
  try { parsed = JSON.parse(text); } catch { throw new Error(`Token endpoint returned non-JSON: ${text.slice(0, 200)}`); }
  if (!parsed.access_token) throw new Error("Token endpoint response did not contain access_token.");
  return parsed.access_token;
}

async function main() {
  const endpoint = process.env.FOUNDRY_CLAUDE_ENDPOINT;
  const model = process.env.FOUNDRY_CLAUDE_MODEL || "claude-sonnet-4-6";
  const privateEndpointSubnetPrefix = process.env.PRIVATE_ENDPOINT_SUBNET_PREFIX;

  if (!endpoint) throw new Error("FOUNDRY_CLAUDE_ENDPOINT is not configured.");
  if (!privateEndpointSubnetPrefix) throw new Error("PRIVATE_ENDPOINT_SUBNET_PREFIX was not supplied.");

  const host = new URL(endpoint).hostname;
  let dnsResults = [];
  let privateMatches = [];
  for (let i = 0; i < 30; i++) {
    try {
      dnsResults = await dns.lookup(host, { all: true, verbatim: true });
      privateMatches = dnsResults.filter(r => r.family === 4 && inCidr(r.address, privateEndpointSubnetPrefix));
      if (privateMatches.length > 0) break;
      console.log(`[Attempt ${i+1}/30] DNS resolved ${host} to ${dnsResults.map(r => r.address).join(", ")} (not in ${privateEndpointSubnetPrefix}). Retrying in 10s...`);
    } catch (e) {
      console.log(`[Attempt ${i+1}/30] dns.lookup failed for ${host}: ${e.message}. Retrying in 10s...`);
    }
    await new Promise(res => setTimeout(res, 10000));
  }

  if (privateMatches.length === 0) {
    throw new Error(
      `Foundry host ${host} did not resolve into ${privateEndpointSubnetPrefix} after 300s. ` +
      `Last resolved: ${dnsResults.map(r => r.address).join(", ")}`
    );
  }


  const token = await getManagedIdentityToken("https://cognitiveservices.azure.com");

  const fetchUrl = new URL(endpoint);
  if (!fetchUrl.searchParams.has("api-version")) {
    fetchUrl.searchParams.set("api-version", "2024-02-15-preview");
  }

  const response = await fetch(fetchUrl.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "anthropic-version": "2023-06-01",
      Authorization: `Bearer ${token}`,
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

main().then(() => {
  setTimeout(() => process.exit(0), 5000);
}).catch(err => {
  console.error(err.stack || err.message || String(err));
  setTimeout(() => process.exit(1), 5000);
});
NODE

NODE_SCRIPT_B64="$(printf '%s' "$NODE_SCRIPT" | base64 -w 0)"

# Log Analytics workspace ID for log capture (best-effort).
LAW_ID=$(az monitor log-analytics workspace list -g "$RG" --query '[0].customerId' -o tsv 2>/dev/null || echo "")

JOB_YAML="$(mktemp)"
cleanup() {
  rm -f "$JOB_YAML"
  az containerapp job delete --name "$JOB" --resource-group "$RG" --yes 2>/dev/null || true
}
trap cleanup EXIT

# Container Apps console logs land in Log Analytics with 1-3 min of ingestion
# lag, so a single immediate query almost always returns nothing — which is why
# earlier failures were undiagnosable. Poll until the rows appear (or give up).
capture_logs() {
  if [[ -z "$LAW_ID" ]]; then
    echo "(no Log Analytics workspace found; cannot capture container logs)"
    return
  fi
  echo "Capturing container logs (Log Analytics ingestion can lag a few minutes)..."
  for attempt in $(seq 1 9); do
    local rows
    rows=$(az monitor log-analytics query -w "$LAW_ID" \
      --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(15m) | where ContainerJobName_s == '${JOB}' | order by TimeGenerated asc | project Log_s" \
      -o tsv 2>/dev/null || echo "")
    if [[ -n "$rows" ]]; then
      echo "----- ${JOB} container logs -----"
      echo "$rows"
      echo "---------------------------------"
      return
    fi
    echo "  [logs $attempt/9] not yet ingested, waiting 20s..."
    sleep 20
  done
  echo "::warning::Container logs did not appear in Log Analytics within the ingestion window (~3 min)."
}

# az containerapp job create's --command/--args flags cannot express a value
# that starts with "-" (the "-c" for /bin/sh): the CLI's argparse always reads
# it as an unknown flag, never as a list element. The documented, robust path
# is a YAML manifest, where command/args are plain list items immune to CLI
# argument parsing.
# https://learn.microsoft.com/azure/container-apps/azure-resource-manager-api-spec#container-apps-job
echo "Creating validation job $JOB..."
LOCATION=$(az group show --name "$RG" --query location -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

cat > "$JOB_YAML" <<JSON
{
  "location": "${LOCATION}",
  "identity": {
    "type": "UserAssigned",
    "userAssignedIdentities": {
      "${UAI_ID}": {}
    }
  },
  "properties": {
    "environmentId": "${CONTAINER_APP_ENVIRONMENT_ID}",
    "configuration": {
      "triggerType": "Manual",
      "replicaTimeout": 300,
      "replicaRetryLimit": 0,
      "manualTriggerConfig": {
        "replicaCompletionCount": 1,
        "parallelism": 1
      },
      "secrets": [
        {
          "name": "dockerhub-password",
          "value": "${DOCKERHUB_PASSWORD}"
        }
      ],
      "registries": [
        {
          "server": "docker.io",
          "username": "${DOCKERHUB_USERNAME}",
          "passwordSecretRef": "dockerhub-password"
        }
      ]
    },
    "template": {
      "containers": [
        {
          "image": "${WEB_IMAGE}",
          "name": "${JOB}",
          "command": [
            "/bin/sh"
          ],
          "args": [
            "-c",
            "echo \\"\\$VALIDATION_SCRIPT_B64\\" | base64 -d | node"
          ],
          "env": [
            {
              "name": "VALIDATION_SCRIPT_B64",
              "value": "${NODE_SCRIPT_B64}"
            },
            {
              "name": "AZURE_CLIENT_ID",
              "value": "${MANAGED_IDENTITY_CLIENT_ID}"
            },
            {
              "name": "FOUNDRY_CLAUDE_ENDPOINT",
              "value": "${FOUNDRY_ENDPOINT}"
            },
            {
              "name": "FOUNDRY_CLAUDE_MODEL",
              "value": "${FOUNDRY_MODEL:-claude-sonnet-4-6}"
            },
            {
              "name": "PRIVATE_ENDPOINT_SUBNET_PREFIX",
              "value": "${PRIVATE_ENDPOINT_SUBNET_PREFIX}"
            }
          ],
          "resources": {
            "cpu": 0.5,
            "memory": "1Gi"
          }
        }
      ]
    }
  }
}
JSON

az rest --method put \
  --uri "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}/providers/Microsoft.App/jobs/${JOB}?api-version=2024-03-01" \
  --body @"$JOB_YAML"

echo "Starting validation job..."
az containerapp job start --name "$JOB" --resource-group "$RG"

echo "Polling for completion (up to 6 minutes)..."
VALIDATION_STATUS="Running"
for i in $(seq 1 36); do
  EXEC_JSON=$(az containerapp job execution list --name "$JOB" --resource-group "$RG" \
    --query "[-1]" -o json 2>/dev/null || echo "{}")
  STATUS=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('properties',{}).get('status','Running'))" <<< "$EXEC_JSON" 2>/dev/null || echo "Running")
  VALIDATION_STATUS="$STATUS"
  echo "  [$i/36] Status: $STATUS"

  case "$STATUS" in
    Succeeded)
      echo "Foundry private access validation passed."
      exit 0
      ;;
    Failed|Stopped)
      echo "::error::Foundry validation job failed. Capturing logs..."
      capture_logs
      exit 1
      ;;
  esac
  [[ $i -lt 36 ]] && sleep 10
done

echo "::error::Foundry validation job timed out after 6 minutes."
capture_logs
exit 1
