# ADF-003: North-South Egress Inspection

## Status

Accepted

## Context

The current deployment defines no route tables, no forced-tunneling path, and
no centralized egress inspection tier. That means application egress relies on
Azure defaults.

Microsoft guidance for Azure Front Door explicitly distinguishes edge HTTP/S
ingress from non-HTTP and egress controls. Front Door protects public web
ingress. It is not the control plane for general outbound traffic.

For a customer-visible architecture, outbound access should be controlled,
logged, and inspectable.

## Architecture

Recommended egress model:

```text
App subnet
  -> UDR default route (0.0.0.0/0)
Azure Firewall subnet
  -> application rules / network rules / threat intel / logging
Internet or approved private destinations
```

If a hub-and-spoke landing zone exists, the firewall should live in the shared
connectivity plane and spokes should use UDRs to steer traffic to it.

## Decision

Introduce Azure Firewall as the centralized north-south and transit inspection
point and use UDRs to send outbound traffic through it.

Required controls:

1. UDR on workload subnets with `0.0.0.0/0` next hop to Azure Firewall
2. Application rules for outbound FQDN-based dependencies where possible
3. Network rules for non-HTTP/S traffic
4. Diagnostic logging to Log Analytics / SIEM
5. Separate exception handling for Azure PaaS/private endpoints where direct
   routing is intentional

## Flow

1. Workload initiates outbound connection.
2. Subnet UDR overrides Azure default internet route.
3. Traffic is sent to Azure Firewall.
4. Firewall evaluates application/network policy.
5. Allowed traffic egresses; denied traffic is logged and blocked.

## Why this decision

- Microsoft recommends UDR override when steering traffic to a virtual
  appliance.
- Azure Firewall is the Microsoft-native service for centralized inspection of
  non-HTTP and outbound traffic.
- This gives the customer a defensible answer for where egress policy lives.

## Consequences

Positive:

- Centralized outbound policy and observability.
- Better control of data exfiltration paths.
- Clear separation between edge ingress and egress security roles.

Tradeoffs:

- Additional cost and operational complexity.
- Some Azure service dependencies need explicit allowlisting.
- Can increase latency slightly for outbound flows.

## Implementation notes

- Use route tables on app subnets, not on the firewall subnet itself.
- Preserve private endpoint routing behavior intentionally; do not blindly force
  private service traffic onto internet paths.
- Prefer Firewall Premium if TLS inspection or IDPS requirements exist.

## Microsoft guidance

- Azure virtual network traffic routing and UDR behavior:
  https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-udr-overview
- Azure Firewall Well-Architected guidance:
  https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-firewall
- Azure Front Door guidance noting Firewall for non-HTTP and egress:
  https://learn.microsoft.com/en-us/azure/frontdoor/scenarios
