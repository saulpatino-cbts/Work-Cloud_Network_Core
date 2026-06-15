# ADF-007: Private PaaS Connectivity And DNS

## Status

Accepted

## Context

The target architecture should keep Azure PaaS traffic private wherever service
support exists. The current deployment already uses private endpoints and
private DNS for Key Vault and Blob Storage, and uses delegated private access
for PostgreSQL. The next decision is how to standardize this pattern so traffic
stays local to the Azure private network path and does not depend on public
resolution where avoidable.

## Architecture

Recommended target pattern:

```text
Workload subnet
  -> private endpoint or delegated private access
Private endpoint subnet
  -> Key Vault, Storage, future private PaaS endpoints
Database subnet
  -> PostgreSQL delegated private access
Private DNS zones
  -> Azure private endpoint and private service name resolution
```

## Decision

Keep Azure PaaS dependencies private wherever supported and use Azure Private
DNS as the default name-resolution model for those private services.

Specific decisions:

1. Keep Key Vault private via private endpoint.
2. Keep Storage private via private endpoint.
3. Keep PostgreSQL private with delegated subnet access and private DNS.
4. Prefer private networking for additional supported PaaS services.
5. Do not introduce custom DNS unless the customer already has a central DNS
   architecture that must be integrated.

## Flow

1. Workload resolves a private service FQDN.
2. Azure Private DNS resolves the service to a private address.
3. Traffic stays on the VNet/private Azure path to the private endpoint or
   delegated service.
4. NSG and route policy control the allowed workload path.

## Why this decision

- It aligns with Microsoft's private endpoint and private DNS design pattern.
- It keeps service traffic private without adding unnecessary DNS complexity.
- It improves the customer's confidence that internal service dependencies are
  not using public endpoints by default.

## Consequences

Positive:

- Reduces exposed surface for platform dependencies.
- Keeps service-to-service traffic on private paths where supported.
- Simplifies the security explanation for customer review.

Tradeoffs:

- Requires correct private DNS zone linkage and, if present, customer DNS
  forwarding rules.
- Some Azure services still have private-networking feature limitations.

## Implementation notes

- Continue using Azure Private DNS for private endpoint-backed services.
- If customer-managed DNS is mandatory, integrate it by forwarding to Azure
  Private DNS zones rather than replacing the private zone pattern.
- Treat public AI Foundry access as a separately governed exception until the
  selected feature set can be fully privatized.

## Microsoft guidance

- Azure Private Endpoint overview:
  https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview
- Azure Private DNS guidance:
  https://learn.microsoft.com/en-us/azure/dns/private-dns-privatednszone
- PostgreSQL Flexible Server private networking:
  https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-networking-private
