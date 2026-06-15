# ADF-005: Front Door Vs Application Gateway Vs Azure Firewall

## Status

Accepted

## Context

The platform needs a clear networking story for customer environments:

- why Azure Front Door exists
- whether Application Gateway should be added
- why Azure Firewall is still needed if another gateway or WAF exists

These services solve different layers of the problem.

## Architecture

Recommended layered model:

```text
Global edge:
  Azure Front Door Premium

Regional HTTP/S ingress (optional but recommended for strict origin protection):
  Azure Application Gateway WAF v2

Regional east-west / north-south / non-HTTP / egress control:
  Azure Firewall

Private workload subnets:
  web / api / worker / data / private endpoints
```

## Decision

Use the services for separate roles, not as substitutes:

1. Keep Azure Front Door Premium for global public ingress.
2. Add Application Gateway only if we need regional Layer 7 ingress control in
   the VNet, private origins, or a stronger origin-locking pattern behind Front
   Door.
3. Add Azure Firewall for centralized egress and non-HTTP/S inspection. Do not
   expect Front Door or Application Gateway to replace it.

## Flow

### Option A: Minimal acceptable pattern

1. Client -> Front Door
2. Front Door -> locked origin
3. Workload subnets -> Azure Firewall via UDR for outbound

### Option B: Preferred customer-grade pattern

1. Client -> Front Door Premium
2. Front Door -> Application Gateway WAF v2 in regional VNet
3. Application Gateway -> private workload endpoints
4. Workload subnets -> Azure Firewall via UDR for outbound and transit

## Service roles

### Azure Front Door

- Global Layer 7 entry point
- CDN, acceleration, anycast edge, global failover, edge WAF
- Best for internet-facing HTTP/S workloads spanning users or regions

### Azure Application Gateway

- Regional Layer 7 reverse proxy inside or adjacent to the VNet
- Useful for path routing, header-based routing, regional ingress control, and
  private backends
- Good companion behind Front Door when regional ingress policy is needed

### Azure Firewall

- Network security control, not an application delivery controller
- Handles outbound policy, non-HTTP/S inspection, transit control, and central
  logging
- Works with UDRs to enforce routed inspection

## Why Front Door was used instead of only Application Gateway

Using only Application Gateway would give regional ingress, but it would not
provide Front Door's global edge advantages:

- global anycast entry point
- traffic acceleration on Microsoft's backbone
- edge WAF and edge DDoS absorption
- better global user experience and global routing posture

That makes Front Door the better primary public edge for this workload.

## Why Application Gateway can still be needed

Application Gateway is justified when the customer requires:

- regional ingress control inside the VNet
- private backend patterns
- a cleaner way to ensure only Front Door reaches the application tier
- separation between global edge and regional application ingress

If the origin can be securely locked directly to Front Door, Application Gateway
becomes optional rather than mandatory.

## Why Azure Firewall is still needed

Neither Front Door nor Application Gateway is the right control for general
egress and non-HTTP/S traffic.

Azure Firewall is still required when you need:

- outbound allowlisting
- egress inspection
- non-HTTP/S inspection
- transit enforcement between subnets/spokes
- UDR-steered centralized policy

## Recommendation for CNA

Preferred recommendation:

1. Front Door Premium remains the public edge.
2. Add Azure Firewall with UDRs for outbound and transit control.
3. Add subnet-specific NSGs across all subnets.
4. Decide on Application Gateway based on the origin-locking requirement:
   - if direct Front Door origin protection is supportable for the chosen app
     hosting pattern, Application Gateway is optional
   - if not, place Application Gateway behind Front Door and make it the only
     regional HTTP/S ingress

## Microsoft guidance

- Load balancing options:
  https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/load-balancing-overview
- Azure Front Door scenarios:
  https://learn.microsoft.com/en-us/azure/frontdoor/scenarios
- Secure traffic to Azure Front Door origins:
  https://learn.microsoft.com/en-us/azure/frontdoor/origin-security
- Azure Front Door Well-Architected guidance:
  https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-front-door
- Azure Firewall Well-Architected guidance:
  https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-firewall
