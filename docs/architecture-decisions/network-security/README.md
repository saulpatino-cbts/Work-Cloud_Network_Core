# Network Security ADFs

These Architecture, Decision, Flow (ADF) records capture the Azure networking
security decisions for the CNA platform as it moves into customer environments.
The decisions below reflect the approved `0.8 beta` target direction for
implementation. Code-level implementation is in `main`; live customer-like Azure
validation remains tracked in the root `TODO.md`.

## Documents

- `ADF-001-edge-ingress-and-origin-protection.md`
- `ADF-002-east-west-segmentation.md`
- `ADF-003-north-south-egress-inspection.md`
- `ADF-004-ai-foundry-network-isolation.md`
- `ADF-005-front-door-vs-app-gateway-vs-firewall.md`
- `ADF-006-centralized-logging-and-telemetry.md`
- `ADF-007-private-paas-connectivity-and-dns.md`
- `ADF-008-container-apps-workload-profile-for-private-origin.md`
- `ADF-009-private-endpoint-approval-automation.md`
- `ADF-010-virtual-network-flow-logs.md`
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
6. Keep Azure AI Foundry private for the Claude runtime path, with deployment
   validation required for private DNS resolution and managed-identity
   inference.
7. Use a workload profile Container Apps environment for the Front Door private
   origin pattern.
8. Automate provider-side private endpoint approval in the deployment pipeline
   using workload identity and least-privilege Azure access.

## Beta readiness status

- Implemented in Terraform/workflows: ADF-001 through ADF-010.
- Validation gates in workflow `031`: Front Door private endpoint approval,
  Foundry private DNS resolution, Foundry managed-identity inference, Front Door
  health, Application Insights telemetry, and release evidence cataloging.
- Remaining beta work: live `dev` deployment execution, Entra redirect update,
  customer-like assessment validation, and any egress/WAF refinements discovered
  from live logs.
