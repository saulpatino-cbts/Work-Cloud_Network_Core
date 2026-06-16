#!/usr/bin/env bash
set -euo pipefail

: "${RESOURCE_GROUP_NAME:?RESOURCE_GROUP_NAME is required}"
: "${WEB_CONTAINER_APP_NAME:?WEB_CONTAINER_APP_NAME is required}"
: "${PRIVATE_ENDPOINT_SUBNET_PREFIX:?PRIVATE_ENDPOINT_SUBNET_PREFIX is required}"

MAX_ATTEMPTS="${MAX_ATTEMPTS:-12}"
SLEEP_SECONDS="${SLEEP_SECONDS:-20}"

read -r -d '' NODE_SCRIPT <<'NODE' || true
const dns = require("node:dns").promises;
const { URL } = require("node:url");
const { DefaultAzureCredential } = require("@azure/identity");

function ipToInt(ip) {
  const parts = ip.split(".").map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    throw new Error(`Unsupported IPv4 address: ${ip}`);
  }
  return parts.reduce((acc, part) => ((acc << 8) + part) >>> 0, 0);
}

function inCidr(ip, cidr) {
  const [network, prefixText] = cidr.split("/");
  const prefix = Number(prefixText);
  if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) {
    throw new Error(`Invalid CIDR prefix: ${cidr}`);
  }
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return (ipToInt(ip) & mask) === (ipToInt(network) & mask);
}

async function main() {
  const endpoint = process.env.FOUNDRY_CLAUDE_ENDPOINT;
  const model = process.env.FOUNDRY_CLAUDE_MODEL || "claude-sonnet-4-6";
  const privateEndpointSubnetPrefix = process.env.PRIVATE_ENDPOINT_SUBNET_PREFIX;

  if (!endpoint) throw new Error("FOUNDRY_CLAUDE_ENDPOINT is not configured in the web Container App.");
  if (!privateEndpointSubnetPrefix) throw new Error("PRIVATE_ENDPOINT_SUBNET_PREFIX was not supplied.");

  const host = new URL(endpoint).hostname;
  const dnsResults = await dns.lookup(host, { all: true, verbatim: true });
  const privateMatches = dnsResults.filter((result) => result.family === 4 && inCidr(result.address, privateEndpointSubnetPrefix));

  if (privateMatches.length === 0) {
    throw new Error(`Foundry host ${host} did not resolve into ${privateEndpointSubnetPrefix}. Resolved: ${dnsResults.map((result) => result.address).join(", ")}`);
  }

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
  if (!response.ok) {
    throw new Error(`Foundry managed identity inference failed with HTTP ${response.status}: ${body.slice(0, 500)}`);
  }

  console.log(JSON.stringify({
    status: "passed",
    host,
    resolved_addresses: dnsResults.map((result) => result.address),
    private_endpoint_subnet_prefix: privateEndpointSubnetPrefix,
    inference_http_status: response.status,
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
NODE

NODE_SCRIPT_B64="$(printf '%s' "$NODE_SCRIPT" | base64 -w 0)"
REMOTE_COMMAND="/bin/sh -lc \"PRIVATE_ENDPOINT_SUBNET_PREFIX='${PRIVATE_ENDPOINT_SUBNET_PREFIX}' node -e \\\"eval(Buffer.from('${NODE_SCRIPT_B64}','base64').toString())\\\"\""

for ((attempt=1; attempt<=MAX_ATTEMPTS; attempt++)); do
  echo "Validating Foundry private DNS and managed identity inference (${attempt}/${MAX_ATTEMPTS})..."
  if az containerapp exec \
    --name "$WEB_CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --command "$REMOTE_COMMAND"; then
    echo "Foundry private access validation passed."
    exit 0
  fi

  if [[ "$attempt" -lt "$MAX_ATTEMPTS" ]]; then
    echo "Foundry validation did not pass yet; waiting ${SLEEP_SECONDS}s before retry."
    sleep "$SLEEP_SECONDS"
  fi
done

echo "::error::Foundry private DNS or managed identity inference validation failed after ${MAX_ATTEMPTS} attempts."
exit 1
