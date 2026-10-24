# Design — AWS assessment coverage: surpass Azure (BUILD-01)

**Status:** Draft for review. No implementation yet.
**Requirements:** `requirements.md` in this folder.

## Overview

Extend the AWS network collector with a Phase-2-equivalent set of collectors that match and then
exceed the Azure network collector's depth, plus AWS-native telemetry (cost, flow-log analytics,
TGW route analysis) that Azure has no equivalent of. Reuse the existing discovery conventions
exactly — no new patterns.

Grounded in the code as read:
- `cna/modules/network/discovery/aws_discovery.py` — `AWSDiscovery`, cross-account via
  `_assume_role`, per-region `_discover_region`, topology collectors (`_collect_vpcs`,
  `_collect_tgws`, `_collect_tgw_attachments`, `_collect_network_firewalls`, …). This is where the
  new collectors attach.
- `cna/modules/network/discovery/azure_discovery.py` — the Phase 2 reference to match:
  `_run_metrics_scan`, `_run_observability_scan`, `_run_bgp_scan`, `_run_waf_scan`,
  `_collect_defender_assessments`.
- `cna/modules/security/discovery/aws_security.py` — **already** collects Security Hub / GuardDuty /
  Config. Do not duplicate; security posture is done.
- `cna/core/throttle.py` — `with_retry`, `PaginationCursor`, `ConcurrencyLimiter` — mandatory for
  new collectors.
- `cna/core/topology_schema.py` — where new record types (metrics, flow-log summary, TGW route
  analysis, cost) are added.
- `cna/core/discovery_coverage.py` — `DiscoveryCoverageReport` for blocked accounts/regions.
- `cna/core/findings_schema.py` — `est_monthly_cost_usd` + `[VERIFY]` for cost findings.
- `cna/ai_engine/recommendation_engine.py`, `cna/ai_engine/mcp_client/` — DD-003 recommendation
  sourcing + the AWS MCP power (R5).

## New collectors (attach to `AWSDiscovery`)

Each follows the existing shape: a `_collect_*` method taking a boto3 client/session + account +
region, wrapped with `with_retry`, paginated via `PaginationCursor`, returning normalized records,
degrading to empty + logged reason when the service/permission is absent.

### C1 — Network metrics (`_collect_network_metrics`) — R1
- Client: `cloudwatch`.
- For each discovered resource type, `get_metric_data` for a bounded window: NAT gateway
  BytesOut/In, TGW BytesIn/Out, VPN TunnelState, ALB/NLB RequestCount + HTTPCode_ELB_5XX, VPC
  endpoint bytes.
- Record as observed metrics against the resource in the topology schema. Azure parity:
  `_run_metrics_scan`.

### C2 — Flow-log analytics (`_collect_flow_log_analysis`) — R2 (surpass)
- Detects flow-log config per VPC (already partially known); where logs land in CloudWatch Logs or
  S3 and are reachable, run a bounded query (CloudWatch Logs Insights for CW destinations) to
  summarize top talkers, REJECT counts, cross-AZ flows.
- Where not enabled: emit a **gap finding** (not a failure).
- Azure has flow-log *state* only; this is a surpass capability.

### C3 — TGW route analysis (`_collect_tgw_route_analysis`) — R3 (surpass)
- Client: `ec2`. `search_transit_gateway_routes` / describe route tables for each TGW route table
  already discovered; summarize active/blackhole routes, propagations, and overlapping CIDRs across
  attachments.
- Extends the existing `_collect_tgw_attachments` rather than replacing it.

### C4 — Cost telemetry (`_collect_network_cost`) — R4 (surpass)
- Client: `ce` (Cost Explorer), called once per account (not per region) over a bounded window
  (default last 30 days — open question 2).
- Filter to network-attributable usage types (NatGateway-Hours/Bytes, DataTransfer, VpcEndpoint,
  TransitGateway). Attribute to resources where the cost allocation allows; otherwise account-level.
- Record via `est_monthly_cost_usd` with `[VERIFY]`.
- Bounded by date + granularity so the Cost Explorer call cost is known (R4.3).

### C5 — MCP / agent enrichment (R5)
- After collection, optional enrichment: route gap findings through
  `recommendation_engine` + `mcp_client` (the AWS MCP power) for current best-practice
  recommendations (DD-003). Degrades gracefully when the power is absent.

### C6 — FLAGSHIP: Reachability Analyzer path testing (`_collect_reachability_paths`) — R8 (surpass)
- Client: `ec2` — `create_network_insights_path` + `start_network_insights_analysis` +
  `describe_network_insights_analyses`.
- Endpoint pairs are **configurable** with topology-derived **defaults**: public ingress → web
  tier, web → api, app tier → RDS. Each analysis returns reachable / not-reachable plus the blocking
  component, recorded as observed state.
- **This is the one collector that creates a (billable) resource.** It must: tag every path
  `Project=cna`, bound the number of pairs, and **delete** the insights path + analysis after
  reading the result (create → analyze → read → delete, in a finally block). Treated as a documented
  Level-2-style action in `module.yaml` permissions. Degrades to a logged gap when unavailable.
- Azure has no equivalent in the network collector — this is the headline surpass capability.

### Metrics configurability (R1 decision)
C1 takes an optional metric-set override; when absent, a mandatory recommended default set applies
(NAT bytes, TGW bytes, VPN tunnel state, ALB/NLB request+5XX, VPC endpoint bytes). The default is
defined as a module-level constant, not inline at the call site.

### Cost windows (R4 decision)
C4 queries Cost Explorer for **30, 60, and 90-day** windows per account (30 = recent drift / what
changed, 60/90 = trend and quick-win sizing). Three bounded calls, not an unbounded scan.

## Schema additions (`cna/core/topology_schema.py`)

New record types, mirroring how Azure metrics/observability are modeled:
`AWSNetworkMetrics`, `AWSFlowLogSummary`, `AWSTGWRouteAnalysis`, `AWSNetworkCost`. Attached to the
existing `AWSRegionTopology` / `AWSTopology` so the report engine picks them up with no renderer
change.

## Orchestration

In `AWSDiscovery._discover_region` (and once-per-account for cost), call the new collectors after
the existing topology collection, inside the same try/except that records `discovery_blocked` /
`block_reason`. A collector failure degrades that capability, never the whole region. Concurrency
stays within `ConcurrencyLimiter` (default AWS concurrency 10).

## Capability matrix (R6)

Maintain a matrix doc (in this spec folder or the module) listing each network capability with:
Azure has it / AWS has it / AWS exceeds it. Seed:

| Capability | Azure | AWS (today) | AWS (after this) |
|---|---|---|---|
| Topology (VPC/subnet/route/TGW/DX/VPN) | ✅ | ✅ | ✅ |
| Firewall / WAF discovery | ✅ | ✅ | ✅ |
| Security posture (Defender ↔ SecHub/GuardDuty/Config) | ✅ | ✅ (aws_security.py) | ✅ |
| Metrics | ✅ (Phase 2) | ❌ | ✅ (C1) |
| Observability coverage | ✅ (Phase 2) | partial | ✅ (C1/C2) |
| BGP status | ✅ (Phase 2) | ❌ | ✅ (extend VPN/DX) |
| Flow-log **analysis** | ❌ (state only) | ❌ | ✅ **exceeds** (C2) |
| TGW route **analysis** | n/a | ❌ | ✅ **exceeds** (C3) |
| Network **cost** | ❌ | ❌ | ✅ **exceeds** (C4) |

## Testing strategy

- **Unit per collector** with mocked boto3 (botocore Stubber or moto): given canned API responses,
  the collector returns the expected normalized records and degrades to empty + logged reason on
  the `_NOT_ENABLED_CODES`-style errors.
- **Bounded-cost test:** the Cost Explorer collector issues one bounded call, never an unbounded
  scan.
- **Read-only assertion:** no collector calls a mutating API (static check on the allowed action
  list; every call is Describe/Get/List/Search/get_metric_data/get_cost_and_usage).
- **Non-regression:** existing topology collectors and the Azure path unchanged.
- Synthetic/mocked data only — never a real customer account in tests.

## Risks

- **Cost Explorer spend/latency.** CE calls cost money per request; bound the window and granularity
  and call once per account. (R4.3)
- **Flow-log volume.** Insights queries over large flow logs can be slow/expensive; cap the query
  window and result size.
- **Permission breadth.** New reads (cloudwatch, ce, logs:StartQuery) expand the assessment role's
  needs; update the scanner-role scripts and `module.yaml` `required_permissions` accordingly.
- **"Surpass" staying honest.** The matrix (R6) must be evidence-backed, not aspirational.
