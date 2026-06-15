# ADF-006: Centralized Logging And Telemetry

## Status

Accepted

## Context

The current deployment already sends Container Apps platform and workload logs
to a Log Analytics workspace and sends application telemetry to Application
Insights. However, network and security controls such as Front Door, WAF,
virtual network flow logs, private endpoints, Key Vault, Storage, PostgreSQL,
and future Azure Firewall diagnostics are not yet consistently wired into the
same evidence plane.

Because this platform assesses networking and security posture, customer
environments require a clear answer to "where do the logs go?" and a single
queryable place to validate ingress, egress, and east-west controls.

## Architecture

Recommended target pattern:

```text
Platform controls
  -> Front Door, WAF, Azure Firewall, virtual network flow logs, Key Vault, Storage,
     PostgreSQL, Container Apps, private endpoints
  -> Shared Log Analytics workspace

Application signals
  -> Application Insights
  -> Workspace-based correlation and retention where needed
```

## Decision

Use one shared Log Analytics workspace as the central infrastructure, network,
and security evidence store for the deployment, while continuing to use
Application Insights for application telemetry.

Required telemetry sources:

1. Azure Front Door access, WAF, and health diagnostics
2. Azure Firewall application, network, threat intel, and DNS proxy logs
3. Virtual network flow logs with Traffic Analytics
4. Container Apps environment and workload logs
5. Key Vault diagnostic logs
6. Storage diagnostic logs
7. PostgreSQL diagnostic logs
8. Private endpoint and Private DNS diagnostics where available

## Flow

1. Resource emits diagnostic and platform events.
2. Diagnostic settings forward those logs to the shared Log Analytics
   workspace.
3. Application code continues sending traces, dependencies, and exceptions to
   Application Insights.
4. Correlation queries join infrastructure/network evidence with app telemetry
   during investigation.

## Why this decision

- Microsoft recommends centralized observability for operational and security
  investigation.
- Network controls are only defensible if their evidence is retained and
  queryable.
- Customers will expect one authoritative evidence plane for ingress, egress,
  and application behavior.

## Consequences

Positive:

- Consistent incident and audit evidence.
- Easier validation of Firewall, Front Door, and routed network behavior.
- Clear operational separation: Log Analytics for infrastructure/security,
  Application Insights for app telemetry.

Tradeoffs:

- Higher data ingestion cost.
- Requires retention and table-cost review for flow-heavy sources.

## Implementation notes

- Reuse the existing Log Analytics workspace rather than creating multiple
  isolated workspaces for the same environment.
- Keep Application Insights in place; do not replace app telemetry with raw
  workspace logs.
- Right-size retention by signal type, especially for virtual network flow logs and
  Firewall logs.

## Microsoft guidance

- Azure Monitor and Log Analytics overview:
  https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-workspace-overview
- Azure Firewall Well-Architected guidance:
  https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-firewall
- Azure Front Door Well-Architected guidance:
  https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-front-door
