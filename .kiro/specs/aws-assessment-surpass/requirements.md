# Requirements — AWS assessment coverage: surpass Azure (BUILD-01)

**Status:** Draft for review. No implementation yet.
**Tracked by:** issue [Core#71](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/issues/71).
**Origin:** finding CORE-F-01 (`.reports/2026-10-23-core-dual-cloud-assessment-coverage.md`).

## Why we are doing this

The CNA platform assesses both AWS accounts and Azure subscriptions. The review (CORE-F-01) found
the two are genuinely dual-cloud, but the **Azure network discovery is deeper** than the AWS one:
Azure collects a Phase 2 of metrics, BGP status, observability coverage, and Defender assessments
that the AWS network collector does not match.

The user's decision: AWS assessment should **not merely reach parity — it should surpass Azure**,
using Kiro agents and AWS "powers" (the AWS MCP, Cost Explorer, CloudWatch, etc.) to pull *more*
telemetry and metrics than the Azure side does.

## Important scoping correction from code reading

Before planning, two facts from the actual code change the scope:

1. **AWS security posture already exists.** `cna/modules/security/discovery/aws_security.py`
   already collects **Security Hub, GuardDuty, and AWS Config** findings — explicitly built as "the
   AWS analog of Azure Defender." So security posture is **not** the gap. Do not rebuild it; extend
   it only if surpassing Azure requires it.
2. **The gap is concentrated in the network module.** `cna/modules/network/discovery/aws_discovery.py`
   collects topology (VPCs, subnets, route tables, TGWs, Direct Connect, VPN, Network Firewall, WAF)
   but has no equivalent of the Azure collector's Phase 2 (CloudWatch metrics, flow-log analytics,
   TGW route analysis, observability coverage).

So "surpass Azure" concretely means: close the network-depth gap **and** add AWS-native telemetry
Azure has no equivalent of.

## Glossary

- **Account / subscription** — AWS is scanned per *account* (across an Organization via STS
  AssumeRole); Azure per *subscription* (across a tenant). Both already work.
- **Collector** — a method that calls a cloud API and returns normalized records into the topology
  checkpoint (`cna/core/topology_schema.py`).
- **Observed state (DD-002)** — the platform records only what it discovered, never inferences.

## Requirements

### R1 — AWS network metrics (match Azure Phase 2 metrics)
**As an** assessment engineer, **I want** the AWS network collector to gather utilization and
traffic metrics, **so that** an AWS engagement surfaces the same metric-based findings an Azure one
does.

Acceptance criteria:
1. THE SYSTEM SHALL collect CloudWatch metrics for the discovered network resources (at minimum:
   NAT gateway bytes, Transit Gateway bytes, VPN tunnel state, ALB/NLB request and error counts,
   VPC endpoint usage) per account+region.
2. METRICS SHALL be recorded as observed state against the resources they belong to, never inferred.
3. A region/account where a metric is unavailable SHALL degrade gracefully to "no data" with a
   logged reason, exactly as the existing collectors handle a disabled service.

### R2 — VPC flow-log analytics (surpass: Azure has flow-log *state*, we add *analysis*)
**As an** engineer, **I want** the AWS collector to analyze VPC flow logs, **so that** the
assessment reports actual traffic patterns, not just whether logging is enabled.

Acceptance criteria:
1. WHERE VPC flow logs are enabled and reachable, THE SYSTEM SHALL summarize traffic (top talkers,
   rejected-connection counts, cross-subnet/cross-AZ flows) as observed state.
2. WHERE flow logs are not enabled, THE SYSTEM SHALL record that as a finding (a gap), not fail.
3. Flow-log *content* access SHALL be read-only and respect the account's log destination.

### R3 — Transit Gateway route analysis (surpass)
**As an** engineer, **I want** TGW route tables analyzed, **so that** the assessment reports
reachability and blackhole/overlap issues, not just the attachment list.

Acceptance criteria:
1. THE SYSTEM SHALL collect TGW route tables and summarize routes, propagations, blackhole routes,
   and overlapping CIDRs across attachments as observed state.

### R4 — Cost telemetry (surpass: Azure network discovery has no cost dimension)
**As an** engineer, **I want** AWS Cost Explorer data tied to the discovered network resources,
**so that** the assessment can surface cost-of-network findings (NAT gateway spend, cross-AZ
transfer, idle endpoints).

Acceptance criteria:
1. THE SYSTEM SHALL query Cost Explorer for network-attributable spend (NAT, data transfer, VPC
   endpoints, TGW) per account, scoped to a bounded, declared time window.
2. COST figures SHALL be recorded with the existing `est_monthly_cost_usd` + `[VERIFY]` convention
   (static estimate marking).
3. Cost queries SHALL be bounded so scan cost is known and small (no unbounded Cost Explorer calls).

### R5 — Use Kiro agents / AWS powers where they add leverage
**As the** platform, **I want** to use the AWS MCP power and Kiro agents for enrichment, **so that**
recommendations and gap analysis go beyond raw API data.

Acceptance criteria:
1. WHERE an AWS MCP tool or an agent can enrich a finding (e.g. a current best-practice
   recommendation), THE SYSTEM SHALL source it through the existing `recommendation_engine` /
   `mcp_client` path (DD-003: recommendations come from MCP/vendor, not invented).
2. Enrichment SHALL be optional and degrade gracefully when the MCP power is unavailable.

### R6 — Parity-plus accounting
**As a** reviewer, **I want** an explicit capability matrix, **so that** "surpass Azure" is
measurable, not a claim.

Acceptance criteria:
1. THE SYSTEM SHALL maintain a capability matrix (per network capability: Azure has it / AWS has it
   / AWS exceeds it) kept honest and updated as collectors land.
2. EACH new AWS collector SHALL map to the Azure capability it matches or exceeds.

### R7 — Non-regression and safety
Acceptance criteria:
1. New collectors SHALL follow the existing conventions: `with_retry` throttle, `PaginationCursor`,
   per-account concurrency limits, observed-state-only (DD-002), graceful degradation, coverage
   logging (`DiscoveryCoverageReport`).
2. All discovery SHALL remain **read-only** against customer accounts.
3. New collectors SHALL NOT change the Azure path or the existing AWS topology collectors'
   behavior.

## Out of scope

- Rebuilding AWS security posture (already exists in `aws_security.py`).
- Any write/remediation action against a customer account (read-only assessment only).
- The IAM/landingzone/zerotrust module build-out (separate — CORE-F-02/03).

## Decisions (resolved 2026-10-23)

1. **Flagship capability (key):** **AWS Reachability Analyzer path testing** — the collector proves
   actual network reachability between two endpoints (e.g. web subnet → RDS, or ingress → app),
   which the Azure network collector has no equivalent of. This is the headline "surpass"
   capability; the metrics/flow-log/TGW/cost work supports it. Added as R8 below.
2. **Cost windows:** Cost Explorer runs for **30, 60, and 90 days** — oriented at recent drift and
   quick wins (30-day for "what changed," 60/90 for trend). Bounded calls.
3. **Metrics depth:** **configurable metric set, with mandatory recommended defaults.** An
   engagement can override the set, but a sensible default list (R1) always applies if it does not.

### R8 — Flagship: Reachability Analyzer path testing (surpass)
**As an** engineer, **I want** the assessment to test real reachability between key endpoints,
**so that** the report proves connectivity (or proves a break) rather than inferring it from config.

Acceptance criteria:
1. THE SYSTEM SHALL run AWS Reachability Analyzer (VPC Network Access Analyzer / `ec2`
   `create_network_insights_path` + `start_network_insights_analysis`) for a configurable set of
   endpoint pairs derived from the discovered topology (defaults: public ingress → web tier, web
   tier → api, app tier → RDS).
2. RESULTS SHALL be recorded as observed state (reachable / not reachable + the blocking component
   when not), never inferred.
3. Path analyses SHALL be created and cleaned up (they are billable resources); creation is the one
   place the assessment makes a resource, so it SHALL be explicitly bounded, tagged, and torn down,
   and treated as a Level-2-style action documented in the module permissions.
4. WHERE Reachability Analyzer is unavailable or denied, THE capability SHALL degrade to a logged
   gap, not a failure.
