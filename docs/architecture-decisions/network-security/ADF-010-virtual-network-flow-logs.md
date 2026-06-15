# ADF-010: Virtual Network Flow Logs

## Status

Accepted

## Context

The platform needs customer-reviewable network traffic evidence for subnet
segmentation, routed egress, and private-service use. Diagnostic settings alone
do not provide flow-level traffic evidence. Earlier planning referenced NSG
flow logs, but Azure has moved toward virtual network flow logs for new
deployments.

## Architecture

Recommended target pattern:

```text
Virtual network
  -> Virtual network flow logs
  -> Storage account for raw flow data
  -> Traffic Analytics in shared Log Analytics workspace
```

## Decision

Use virtual network flow logs at the VNet level, backed by the existing storage
account and the shared Log Analytics workspace for Traffic Analytics.

Do not introduce new NSG flow logs for this architecture.

## Flow

1. Azure Network Watcher captures Layer 4 traffic at the virtual network scope.
2. Raw flow records are written to the environment storage account.
3. Traffic Analytics processes the flow stream into the shared Log Analytics
   workspace.
4. Operators query the shared workspace for egress verification, lateral-flow
   investigation, and deployment validation.

## Why this decision

- Microsoft recommends virtual network flow logs over new NSG flow logs.
- VNet-level capture is a better fit for customer review because it covers the
  routed workload path rather than only individual NSG attachments.
- Traffic Analytics stays aligned with the existing shared evidence plane.

## Consequences

Positive:

- Current Microsoft-aligned flow logging model.
- Better visibility into routed traffic across the deployment VNet.
- Cleaner investigation path for Firewall and subnet policy validation.

Tradeoffs:

- Additional storage and analytics ingestion cost.
- Higher flow volume than narrowly scoped subnet-only logging.

## Implementation notes

- Keep raw flow log storage in the environment storage account already managed
  by Terraform.
- Keep Traffic Analytics pointed at the same Log Analytics workspace used by
  the rest of the platform diagnostics.
- Avoid enabling overlapping NSG flow logs on the same workloads.

## Microsoft guidance

- Flow logging for network security groups:
  https://learn.microsoft.com/en-us/azure/network-watcher/nsg-flow-logs-overview
- Virtual network flow logs:
  https://learn.microsoft.com/en-us/azure/network-watcher/vnet-flow-logs-overview
- Flow logs ARM/AzAPI resource reference:
  https://learn.microsoft.com/en-us/azure/templates/microsoft.network/networkwatchers/flowlogs
