# Network Security ADFs

These Architecture, Decision, Flow (ADF) records capture the Azure networking
security decisions for the CNA platform as it moves into customer environments.
The decisions below now reflect the approved target direction for implementation.

## Documents

- `ADF-001-edge-ingress-and-origin-protection.md`
- `ADF-002-east-west-segmentation.md`
- `ADF-003-north-south-egress-inspection.md`
- `ADF-004-ai-foundry-network-isolation.md`
- `ADF-005-front-door-vs-app-gateway-vs-firewall.md`
- `ADF-006-centralized-logging-and-telemetry.md`
- `ADF-007-private-paas-connectivity-and-dns.md`
- `IMPLEMENTATION-PLAN.md`

## Current recommendation set

1. Keep Azure Front Door Premium as the global public edge.
2. Use Azure Firewall for centralized egress inspection and control via UDRs.
3. Apply subnet-specific NSGs to enforce east-west least privilege.
4. Centralize infrastructure, network, security, and application logging into a
   shared Log Analytics workspace while continuing to use Application Insights
   for app telemetry.
5. Keep Azure PaaS dependencies private wherever supported and use private DNS
   resolution patterns inside the VNet.
6. Reduce Azure AI Foundry public exposure unless there is an approved business
   exception.
