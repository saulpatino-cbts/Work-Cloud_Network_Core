# ADF-004: Azure AI Foundry Network Isolation

## Status

Accepted

## Context

The original Terraform kept Azure AI Foundry publicly reachable and enabled
local authentication. That posture was weaker than the rest of the platform's
private-service model and would draw immediate customer review attention.

Because customers can see architectural resources, this service will likely draw
security review attention even if the application itself is otherwise private.

## Architecture

Recommended target pattern:

```text
Application subnet
  -> private endpoint path to AI Foundry account
Azure AI Foundry
  -> private endpoint plus disabled public network access
Identity
  -> Entra-based auth preferred over local key reliance
```

## Decision

Use private endpoint isolation for the Foundry account, disable public network
access, and disable local authentication. CNA workloads should use Microsoft
Entra tokens via managed identity by default, with API-key fallback treated as
temporary compatibility only.

## Flow

1. CNA workload resolves the Foundry custom subdomain through private DNS.
2. Traffic reaches the Foundry account through the private endpoint on the
   private-endpoint subnet.
3. Runtime authenticates with Microsoft Entra token obtained by managed
   identity.
4. Diagnostics and Log Analytics retain the service evidence.

## Why this decision

- It aligns the AI service path with the rest of the private-data architecture.
- It reduces customer concern about a public AI dependency.
- It improves the story for regulated or security-sensitive deployments.

## Consequences

Positive:

- Smaller exposed surface.
- Better alignment with private-service architecture.
- Easier customer review for sensitive environments.

Tradeoffs:

- Foundry feature support still needs periodic review as the service evolves.
- Operator workflows that rely on direct public portal reachability must use
  approved network paths instead of assuming unrestricted internet access.

## Implementation notes

- Private DNS must resolve the Foundry custom subdomain to the private endpoint
  IP from inside the CNA virtual network.
- The CNA app runtime must prefer managed identity over API-key headers before
  local authentication is disabled.

## Microsoft guidance

- Configure network isolation for Microsoft Foundry:
  https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link
