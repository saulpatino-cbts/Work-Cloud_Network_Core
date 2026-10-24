# AWS vs Azure network assessment — capability matrix (BUILD-01 R6)

Kept honest and evidence-backed: a capability is "AWS ✅" only when a collector
exists in code and is unit-tested. "AWS exceeds" means Azure's network collector
has no equivalent. Updated as collectors land.

**Status: BUILD-01 collectors implemented and unit-tested (mocked boto3). Not
yet run against a live AWS account — the live run belongs to the AWS appliance's
first-deploy work.**

| # | Capability | Azure (network collector) | AWS before | AWS now | Evidence |
|---|---|---|---|---|---|
| 1 | Topology (VPC/subnet/route/TGW/DX/VPN) | ✅ | ✅ | ✅ | `aws_discovery.py` |
| 2 | Firewall / WAF discovery | ✅ | ✅ | ✅ | `aws_discovery.py` |
| 3 | Security posture (Defender ↔ SecHub/GuardDuty/Config) | ✅ | ✅ | ✅ | `aws_security.py` (pre-existing) |
| 4 | Network metrics | ✅ (Phase 2) | ❌ | ✅ **C1** | `aws_metrics.py`, `test_aws_metrics.py` |
| 5 | Flow-log **analysis** (traffic, not just state) | ❌ (state only) | ❌ | ✅ **exceeds (C2)** | `aws_network_depth.FlowLogAnalyzer` |
| 6 | TGW route **analysis** (blackholes, overlaps) | n/a | ❌ | ✅ **exceeds (C3)** | `aws_network_depth.TransitGatewayRouteAnalyzer` |
| 7 | Network **cost** (30/60/90-day) | ❌ | ❌ | ✅ **exceeds (C4)** | `aws_cost.py`, bounded Cost Explorer |
| 8 | **Reachability path testing** (FLAGSHIP) | ❌ | ❌ | ✅ **exceeds (C6)** | `aws_network_depth.ReachabilityAnalyzer` — real endpoint-to-endpoint reachability |

## How "surpass" is substantiated

- **Match:** AWS now collects network metrics (C1), closing the one depth gap
  CORE-F-01 identified against Azure's Phase 2.
- **Exceed:** four capabilities Azure's network collector does not have —
  flow-log traffic analysis (C2), TGW route analysis (C3), network cost (C4),
  and the flagship reachability path testing (C6). The flagship is the headline:
  it proves real connectivity (or proves the break and names the blocking
  component), rather than inferring reachability from configuration.

## Safety notes carried by the matrix

- Every collector is read-only except C6, which creates one network-insights
  path + analysis per tested pair and **always** deletes both (teardown in a
  `finally` block; verified by `test_aws_network_depth.py`).
- C4 is bounded: one Cost Explorer call per window (three per account), monthly
  granularity, explicit date range — no unbounded scans.
- All collectors degrade gracefully (a note on the record) when a service is
  not enabled or access is denied; none fails the region.
