# Tasks — AWS assessment coverage: surpass Azure (BUILD-01)

**Status:** Draft for review. No implementation yet.
**Requirements:** `requirements.md`. **Design:** `design.md`.

All work is in the Core repo, read-only against customer accounts, following the existing discovery
conventions (`with_retry`, `PaginationCursor`, observed-state-only, graceful degradation,
coverage logging).

- [x] 1. Schema additions in `cna/core/topology_schema.py`: `AWSNetworkMetric`, `AWSFlowLogSummary`,
  `AWSTGWRoute`/`AWSTGWRouteAnalysis`, `AWSNetworkCost`, `AWSReachabilityPath`; attached to
  `AWSRegionTopology` / `AWSTopology`. _(R1–R4, R8)_

- [x] 2. C1 — `AWSMetricsCollector` (`aws_metrics.py`), configurable set + mandatory DEFAULT_METRICS,
  bounded window, observed state, graceful degradation. `test_aws_metrics.py` (11). _(R1, R7)_

- [x] 3. C3 — `TransitGatewayRouteAnalyzer` (`aws_network_depth.py`): routes, blackholes, CIDR
  overlaps. Tested. _(R3, R7)_

- [x] 4. C2 — `FlowLogAnalyzer`: summarizes enabled flow logs (top talkers from a bounded Insights
  query); records the gap when disabled; read-only. Tested. _(R2, R7)_

- [x] 5. C4 — `AWSCostCollector` (`aws_cost.py`), once per account, **30/60/90-day** bounded windows,
  network usage-type filter. Tested incl. bounded-call assertion. _(R4, R7)_

- [x] 6. Orchestration: `AWSDiscovery._collect_surpass_depth` called from `_discover_region`
  (C1–C3), behind `DiscoveryOptions.collect_surpass_depth` (default off). Fault in a depth
  collector degrades (warns) without losing the region — tested. _(R7)_

- [ ] 7. C5 — optional MCP/agent enrichment through `recommendation_engine` + `mcp_client` (AWS MCP
  power), DD-003, graceful when absent. **Not yet done** — enrichment layer is the remaining piece;
  the collectors produce the observed data it would enrich.

- [x] 7b. **FLAGSHIP** C6 — `ReachabilityAnalyzer`: configurable endpoint pairs (`default_endpoint_pairs`
  helper), create → analyze → read → **delete** in a `finally` block, tagged `Project=cna`, degrades
  to `reachable=None` when unavailable. Teardown-always verified by tests (success path AND
  mid-analysis error path). _(R8)_

- [x] 8. Permissions: `cna/modules/network/module.yaml` `required_permissions.aws` extended with the
  new reads + the bounded Reachability create/delete pair. (Appliance scanner-role script
  `New-CnaAwsAssessmentRole.ps1` update is a cross-repo item — see note below.) _(R7)_

- [x] 9. Capability matrix doc (`capability-matrix.md`) created, each collector mapped to the Azure
  capability it matches/exceeds. _(R6)_

- [x] 10. Non-regression: existing AWS discovery/security/topology/persistence tests unchanged
  (default-off path); read-only assertion in `test_aws_metrics.py`; teardown assertions in
  `test_aws_network_depth.py`. _(R7)_

- [x] 11. Docs/CHANGELOG: entry added (below). _(done)_

## Remaining / cross-repo

- **Task 7 (C5 MCP enrichment)** — not built; optional, degrades-absent by design. Follow-up.
- **Scanner-role permissions are a CROSS-REPO item.** The new AWS permissions in `module.yaml` must
  be granted by the appliance scanner-role script `New-CnaAwsAssessmentRole.ps1` (AWS appliance) and
  the equivalent Azure scanner role is unaffected (these are AWS-only reads). Per the cross-repo
  rule, a handover note goes to the AWS appliance so its scanner role grants
  cloudwatch/ce/logs/ec2-insights before this runs live.
- **Live run** against a real AWS Organization is out of scope here (AWS appliance first-deploy).

## Verification

- "Done" = tasks 1–11 complete; every new collector unit-tested with mocked boto3 (no real
  account); the read-only assertion passes; the capability matrix shows AWS matching Azure on
  metrics/observability/BGP and exceeding it on flow-log analysis, TGW route analysis, and cost; the
  Azure path and existing AWS topology collectors are unchanged.
- Blocked-on-account items (a real live run against an AWS Organization) are out of scope here and
  belong with the AWS appliance's first-deploy work — this spec is the core collector build, which
  is fully testable with mocks.

## Decisions needed before implementation (from requirements open questions)

1. The "surpass" bar / flagship capability.
2. Default Cost Explorer window (proposed: 30 days).
3. Fixed vs configurable metric set.
