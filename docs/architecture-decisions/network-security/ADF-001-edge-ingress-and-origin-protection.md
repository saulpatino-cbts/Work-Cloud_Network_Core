# ADF-001: Edge Ingress And Origin Protection

## Status

Accepted

## Context

The current Terraform makes `cna-web` externally reachable and uses Azure Front
Door as a public edge in front of the web Container App. That gives global edge
routing and WAF, but it also leaves a direct-origin path that can bypass Front
Door if the backend hostname is discovered.

Microsoft guidance is explicit that Azure Front Door security benefits only
fully apply when traffic flows only through Front Door. Microsoft recommends
either:

- Private Link between Front Door Premium and the origin when supported, or
- source restriction with the `AzureFrontDoor.Backend` service tag plus
  validation of the `X-Azure-FDID` header when public origins are used.

## Architecture

Recommended target pattern:

```text
Client
  ->
Azure Front Door Premium
  -> WAF, bot protection, global TLS, rate limiting, caching
Regional protected ingress
  -> Application Gateway WAF v2 or another origin-lockable regional ingress
Private application backends
  -> web, api, worker, data services
```

Regional ingress is optional only if the chosen origin type can be locked to
Front Door directly in a supportable way.

## Decision

Adopt a "Front Door is the only public entry point" rule.

Preferred order:

1. Use Azure Front Door Premium with Private Link to the origin if the final
   origin type supports it.
2. If direct Private Link from Front Door to the application tier is not
   supportable, place Azure Application Gateway WAF v2 in the regional VNet and
   make it the protected Front Door origin.
3. Do not leave the application origin publicly reachable without Front
   Door-specific restrictions.

## Flow

1. Client connects to Front Door over HTTPS.
2. Front Door applies WAF, DDoS absorption, bot/rate controls, and routing.
3. Front Door forwards only to the approved regional origin.
4. Regional origin accepts traffic only from Front Door.
5. Regional origin forwards to private application backends.

## Why this decision

- Front Door is the Microsoft-recommended global edge for public web traffic.
- The platform needs global ingress, TLS offload, and WAF at the edge.
- Customer-visible architecture should not expose a bypass path around the edge
  security layer.

## Consequences

Positive:

- Removes direct-origin bypass.
- Keeps global edge performance and WAF benefits.
- Creates a cleaner story for customer security review.

Tradeoffs:

- Higher complexity and cost than a direct public Container App origin.
- If Application Gateway is introduced, there is an extra regional hop and
  another WAF/admin surface.

## Implementation notes

- Current repo issue: `web` ingress is public, so origin bypass remains
  possible.
- If Application Gateway is introduced, lock it to Front Door by allowing the
  `AzureFrontDoor.Backend` service tag and validating `X-Azure-FDID`.

## Microsoft guidance

- Azure Front Door scenarios:
  https://learn.microsoft.com/en-us/azure/frontdoor/scenarios
- Secure traffic to Azure Front Door origins:
  https://learn.microsoft.com/en-us/azure/frontdoor/origin-security
- Azure Front Door Well-Architected guidance:
  https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-front-door
