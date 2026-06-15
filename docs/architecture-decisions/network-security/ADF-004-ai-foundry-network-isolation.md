# ADF-004: Azure AI Foundry Network Isolation

## Status

Accepted

## Context

The current Terraform keeps Azure AI Foundry publicly reachable and enables
local authentication. That may be acceptable for development velocity, but it is
weaker than the rest of the platform's private-service posture.

Because customers can see architectural resources, this service will likely draw
security review attention even if the application itself is otherwise private.

## Architecture

Recommended target pattern:

```text
Application subnet
  -> private or tightly controlled access path to AI Foundry
Azure AI Foundry
  -> private endpoint / network isolation where supported
Identity
  -> Entra-based auth preferred over broad local key reliance
```

## Decision

Treat public AI Foundry exposure as an exception, not the default.

Preferred order:

1. Use private networking / private link isolation for Foundry where the
   selected feature set supports it.
2. Disable public network access when the platform and deployment model allow.
3. Prefer managed identity or Entra-based access patterns over local auth where
   support exists.
4. If public access must remain enabled, document the reason, restrict callers
   as much as possible, and treat it as an explicit risk acceptance.

## Flow

1. CNA workload requests model access.
2. Request uses approved identity path.
3. Traffic stays on private connectivity when supported.
4. Audit logs and service diagnostics record access.

## Why this decision

- It aligns the AI control plane with the rest of the private-data architecture.
- It reduces customer concern about a public AI dependency.
- It improves the story for regulated or security-sensitive deployments.

## Consequences

Positive:

- Smaller exposed surface.
- Better alignment with private-service architecture.
- Easier customer review for sensitive environments.

Tradeoffs:

- Some Foundry features still have private-networking caveats.
- Hosted-agent and related scenarios can require public access for dependent
  services.

## Implementation notes

- Validate the exact Foundry feature set before disabling public network access.
- If public access remains enabled short term, mark that as a temporary
  exception in deployment documentation.

## Microsoft guidance

- Configure network isolation for Microsoft Foundry:
  https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link
