# ADF-002: East-West Segmentation

## Status

Accepted

## Context

The current Azure deployment associates one shared NSG to the Container Apps,
private endpoint, and database subnets. The shared NSG contains almost no
subnet-specific policy, which means Azure default `AllowVNetInBound` behavior
still permits broad lateral movement inside the VNet unless more specific rules
are added.

For a customer-hosted assessment platform, east-west traffic should be
intentionally minimized:

- web should talk only to the required application endpoints
- api and worker should talk only to required private services
- database should accept only approved application flows
- private endpoint subnet should not become a general-purpose transit space

## Architecture

Recommended subnet model:

```text
Ingress subnet
  -> Front Door origin or Application Gateway

App subnet
  -> web / api / worker runtime

Private endpoint subnet
  -> Key Vault, Storage, future private PaaS endpoints

Data subnet
  -> PostgreSQL delegated subnet
```

Each subnet gets its own NSG and its own explicit policy intent.

## Decision

Move from one shared NSG to subnet-specific NSGs with deny-by-exception
thinking.

Required controls:

1. App subnet NSG
   - allow only required inbound from the ingress tier
   - allow only required outbound to database, private endpoints, DNS, and
     Azure platform dependencies
2. Private endpoint subnet NSG
   - allow only application-originated flows to approved private endpoints
3. Database subnet NSG
   - allow only database port access from approved app components
4. Explicit deny rules where customer policy requires proof of segmentation

## Flow

1. Regional ingress receives HTTP/S.
2. Only approved app paths are allowed into the app subnet.
3. App subnet can reach only the database subnet and approved private endpoint
   services on required ports.
4. Database subnet returns traffic only for established allowed flows.
5. No other lateral movement path is considered acceptable by default.

## Why this decision

- Microsoft NSGs include default VNet allow rules; custom policy must override
  them when tighter segmentation is required.
- Customer environments typically expect subnet intent to be visible and
  auditable.
- One shared NSG makes it difficult to prove least privilege.

## Consequences

Positive:

- Better lateral-movement resistance.
- Clearer auditability by subnet role.
- Easier policy review with customer security teams.

Tradeoffs:

- More rules and more change management.
- Requires validation of Azure platform dependencies and health probes so
  rules do not accidentally break the service.

## Implementation notes

- Use service tags and augmented rules where possible to keep policy readable.
- Preserve required Azure infrastructure access for health, metadata, and
  platform dependencies.
- Treat the private endpoint subnet as a controlled service-access subnet, not a
  general-purpose workload subnet.

## Microsoft guidance

- NSG overview and default rules:
  https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview
- IP planning and dedicated subnet guidance:
  https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/plan-for-ip-addressing
