# ADF-008: Container Apps Workload Profile Requirement For Front Door Private Origin

## Status

Accepted

## Context

The approved edge pattern is Azure Front Door Premium with a private origin to
Azure Container Apps. Microsoft documents this specific integration as
supported only for Container Apps **workload profile environments**. The
integration also expects the Container Apps managed environment public network
access setting to be disabled while the application ingress remains enabled so
Front Door can reach it over the private endpoint path.

This means the earlier "public Front Door to public Container App FQDN" design
is no longer sufficient for the customer-reviewed target state.

## Architecture

```text
Client
  ->
Azure Front Door Premium
  -> WAF, TLS, routing
Private endpoint in Azure Front Door managed network
  ->
Azure Container Apps managed environment
  -> public network access Disabled
  -> workload profile environment
  -> web app ingress enabled for Front Door private path
Private east-west services
  -> api, worker, database, private endpoints
```

## Decision

Standardize the CNA web tier on a workload profile Container Apps environment
for the Front Door private-origin pattern.

Required characteristics:

1. Use a workload profile environment for the Container Apps managed
   environment.
2. Set managed environment public network access to `Disabled`.
3. Keep the web application ingress enabled so Azure Front Door can terminate
   at the private origin path.
4. Treat this as the baseline architecture for both dev and prod so the deploy
   path stays consistent.

## Flow

1. Terraform creates or updates the workload profile Container Apps
   environment.
2. Terraform disables public network access on the managed environment.
3. Front Door creates a private-link-backed origin targeting the managed
   environment subresource `managedEnvironments`.
4. After approval, client traffic reaches Front Door publicly and traverses the
   Microsoft backbone privately to the Container Apps environment.

## Why this decision

- Microsoft documents the Front Door to Container Apps private-origin pattern
  only for workload profile environments.
- The target customer posture requires elimination of direct-origin bypass.
- Keeping dev and prod aligned reduces deployment drift and review confusion.

## Consequences

Positive:

- Aligns the implementation with Microsoft-supported ingress hardening.
- Removes dependence on public origin exposure for the web tier.
- Produces a stronger customer-facing architecture story.

Tradeoffs:

- Migrating an existing environment to the required shape may require careful
  rollout sequencing or recreation planning.
- Workload profile environments introduce additional design decisions around
  profile type, scaling, and subnet sizing over time.

## Implementation notes

- The current Phase 1 branch changes already reflect this direction in the
  shared compute module and both Azure environment roots.
- Validation must include Front Door health probes, sign-in callback behavior,
  and confirmation that the managed environment is not publicly reachable.

## Microsoft guidance

- Access an Azure container app using an Azure Front Door with Private Link:
  https://learn.microsoft.com/en-us/azure/container-apps/how-to-integrate-with-azure-front-door
- Secure your origin with Private Link in Azure Front Door Premium:
  https://learn.microsoft.com/en-us/azure/frontdoor/private-link
