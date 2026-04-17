# CNA Beta Readiness · Missing Metrics · 10-Page Assessment Gap Analysis

> **Audience:** Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert
> **Last updated:** 2026-04-17 · commit `1907596`
> **Scope:** MVP-Cloud_Network_Assessment @ `main`
> **Persona applied:** Senior Network Architect using CNA to produce a client-deliverable 10-page assessment

---

## Part 1 — Repeatable Deployment: What Needs to Change

### 1.1 Confirmed Working ✅

The deployment sequence (000 → 010 → 030 → 031) is sound. The Terraform state isolation
(separate `rg-cna-tfstate`) is properly designed. The two-pass 031 pattern is documented
correctly in README and TODO. `KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME` are now
written automatically to GitHub Variables after `terraform apply`.

### 1.2 Deployment Gap Status

| # | Issue | Status |
|---|---|---|
| 1 | `azure_network.py` and `azure_security.py` are stubs | ✅ Both now raise `NotImplementedError` with clear message |
| 2 | `CNA_MCP_SERVER_URL` not documented | ✅ Added to `.env.example` and `secrets-reference.md` as `none` |
| 3 | Node.js Dockerfile base image not SHA-pinned | ❌ **Open** — `cna-web/Dockerfile` still uses `node:20-alpine` without digest |
| 4 | `KEY_VAULT_NAME` / `APPLICATION_INSIGHTS_NAME` required manual update | ✅ Auto-written by `031-deploy-azure.yml` step after `terraform apply` |
| 5 | `gitleaks-action` pinned to mutable `v2` tag | ✅ Pinned to SHA `ff98106e` in `020-test-codebase.yml` |
| 6 | Private Endpoint IP resolution empty | ✅ NIC GET implemented — `private_ip_addresses` populated |
| 7 | `vpn_client_pools` list-of-lists bug | ✅ `.extend()` used — flattened correctly |
| 8 | Terraform `prod` environment parity unverified | ❌ **Open** — run `diff dev/ prod/` before first prod promote |

**2 of 8 deployment gaps remain open.**

---

## Part 2 — Networking Metrics Coverage

### 2.1 What You Have Today

| Metric | Source | Status |
|---|---|---|
| Gateway ingress/egress bytes (24h) | Azure Monitor – `TunnelIngressBytes`, `TunnelEgressBytes` | ✅ Collected |
| Gateway throughput utilization % | Azure Monitor – `AverageBandwidth` vs SKU ceiling | ✅ Collected — `GatewayMetric.utilization_pct` populated |
| NSG flow log enable/disable state | Network Watcher API | ✅ Collected |
| Traffic Analytics state per flow log | `flow_analytics_configuration.enabled` | ✅ Collected — `ObservabilityData.traffic_analytics_enabled` |
| BGP peer state + route counts | VPN Gateway API | ✅ Collected |
| ER circuit bandwidth (provisioned) | ARM property `bandwidth_in_mbps` | ✅ Collected |
| ER gateway connection bytes (cumulative) | `AzureGatewayConnection.egress_bytes_transferred` | ✅ Collected |
| Azure Firewall throughput + rule hits | Azure Monitor – `DataProcessed`, `ApplicationRuleHit`, `NetworkRuleHit`, `NatRuleHit` | ✅ Collected — `FirewallMetric` |
| Load Balancer SNAT metrics | Azure Monitor – `UsedSnatPorts`, `AllocatedSnatPorts` | ✅ Collected — `LoadBalancerMetric` |
| VNet IP space utilization % | Calculated from CIDR data | ✅ Collected — `NetworkMetrics.vnet_utilization` |
| Subnet type classification | Derived from NSG + UDR + delegation + outbound | ✅ Collected — `AzureSubnet.subnet_type` |
| Firewall diagnostic settings | ARM diagnostic settings API | ✅ Collected — `ObservabilityData.firewalls_with_diagnostics` |
| Bastion diagnostic settings | ARM diagnostic settings API | ✅ Collected — `ObservabilityData.bastion_with_diagnostics` |

### 2.2 Still Missing

#### 🔴 Tier 1: Still Required for Full Assessment

| Metric | API / Source | Gap Impact |
|---|---|---|
| **NSG flow log traffic volume (east-west bytes)** | Log Analytics: `AzureNetworkAnalytics_CL \| summarize by FlowType_s` | East-west section is config-only. Without this, Page 3 has zero traffic evidence. |
| **ER circuit utilization (actual throughput)** | Azure Monitor on ER circuit: `PrimaryBitsInPerSecond`, `SecondaryBitsInPerSecond` | Cannot confirm a 1Gbps circuit isn't saturated. Blocks Page 6 authoritative verdict. |
| **DDoS attack telemetry** | Azure Monitor: `IfUnderDDoSAttack`, `DdosPacketsDropped` on Public IP resources | Required for NIST IR.RP compliance statements. |

#### 🟡 Tier 2: High Value, Not Yet Collected

| Metric | API / Source | Notes |
|---|---|---|
| **Azure Cost Management — network egress spend** | `azure-mgmt-costmanagement` / `Microsoft.CostManagement/query` | Billing proxy for east-west throughput. `NetworkMetrics.egress_cost_usd_mtd` field exists in schema — collector not yet wired. Works with Billing Reader (no Monitor permissions needed). |
| **Application Gateway capacity units + latency** | Azure Monitor: `CapacityUnits`, `BackendLastByteResponseTime` | WAF efficacy check — latency spike = OWASP rule performance degradation. |
| **Private Endpoint DNS resolution validation** | Network Watcher Connectivity check API | Confirms PE DNS resolves to RFC 1918, not public IP — required for zero-trust PE bypass finding. |
| **Front Door WAF policy (customer tenant)** | `Microsoft.Network/frontDoorWebApplicationFirewallPolicies/read` | CNA assesses App GW WAF but not customer-tenant Front Door WAF policy. |

---

## Part 3 — Senior Architect's 10-Page Assessment: Data Sufficiency Audit

### Page 1: Executive Summary · ✅ Complete

| Required Content | Status |
|---|---|
| Risk score with scoring rationale | ✅ Derived from findings severity counts |
| Organization overview (subscriptions, VNets, locations) | ✅ `AzureTopology.subscriptions[*]` |
| Critical findings summary | ✅ `FindingsReport.critical_count` + `CRITICAL` findings |
| Business impact statement | ✅ AI generates from topology context |
| Assessment scope and methodology | ✅ Hardcoded section in report engine |

---

### Page 2: Network Topology Overview (North-South) · ✅ ~90% Complete

| Required Content | Status | Gap |
|---|---|---|
| Internet ingress paths (Front Door, App GW, Public IPs) | ✅ Complete | — |
| Egress paths (NAT GW, Firewall, public IPs on NICs) | ✅ Complete | — |
| WAN connectivity (VPN connections, ER circuits) | ✅ Complete | — |
| Hybrid connectivity map (on-prem reachability) | ✅ Complete | — |
| Traffic volume / throughput actuals | ✅ `AverageBandwidth` now collected → `utilization_pct` | — |
| Firewall rule utilization | ✅ `DataProcessed` + rule hit counts collected | — |
| DDoS events | ⚠️ State collected, attack history not | ❌ `IfUnderDDoSAttack` / `DdosPacketsDropped` not yet collected |

**Verdict: ✅ Page 2 is defensible. DDoS telemetry is the only remaining gap.**

---

### Page 3: East-West Traffic Analysis · ⚠️ ~65% Complete

| Required Content | Status | Gap |
|---|---|---|
| VNet peering topology (hub-spoke vs mesh) | ✅ Complete | — |
| Spoke-to-spoke path analysis (firewall bypass?) | ✅ AZ-NET-012 implemented | — |
| Route table inspection (UDR forcing through NVA?) | ✅ Complete | — |
| NSG rule analysis (inter-subnet, lateral movement) | ✅ Complete | — |
| Virtual WAN routing | ✅ Complete | — |
| **Actual east-west byte counts** | ❌ Not collected | ❌ `AzureNetworkAnalytics_CL` Log Analytics query not yet wired |
| SNAT exhaustion risk | ✅ LB SNAT metrics collected → AZ-NET-010 | — |

**Verdict: ⚠️ Page 3 config analysis is complete but traffic telemetry (NTA) is still missing. NSG flow log analytics query is the single remaining blocker for a fully evidence-bound east-west section.**

---

### Page 4: Network Segmentation Analysis · ✅ ~95% Complete

| Required Content | Status | Gap |
|---|---|---|
| Subnet classification (public/private/isolated) | ✅ `_classify_subnet()` sets `SubnetType` on every subnet | — |
| NSG coverage (% of subnets with NSG) | ✅ AZ-NET-002 | — |
| Application Security Groups usage | ✅ `source_asgs` / `destination_asgs` in `NSGSecurityRule` | — |
| Service Endpoint vs Private Endpoint strategy | ✅ Complete | — |
| Private Endpoint DNS correctness | ✅ PE IPs collected via NIC GET | ⚠️ DNS resolution *validation* (Network Watcher connectivity check) not yet done |
| Subnet delegation analysis | ✅ `subnet.delegation` field | — |
| Inter-region segmentation | ✅ Multi-subscription merge | — |
| Management plane segmentation | ✅ `ManagementGroup` tree | — |

**Verdict: ✅ Page 4 is effectively complete. PE DNS validation is a nice-to-have, not a blocker.**

---

### Page 5: North-South Security Controls · ✅ ~90% Complete

| Required Content | Status | Gap |
|---|---|---|
| Azure Firewall configuration (SKU, tier, threat intel) | ✅ Complete | — |
| Azure Firewall diagnostic logging | ✅ AZ-NET-013 | — |
| WAF governance (App GW WAF mode, rule set version) | ✅ Complete | — |
| Front Door WAF (customer tenant) | ❌ Not collected | ❌ Requires `frontDoorWebApplicationFirewallPolicies/read` |
| DDoS protection standard enrollment | ✅ Complete | — |
| Public IP exposure inventory | ✅ Complete | — |
| SSL/TLS policy enforcement (App GW) | ✅ Complete | — |
| NVA / 3rd-party NGFW presence | ✅ Complete | — |

**Verdict: ✅ Page 5 is strong. Front Door WAF collection is the only remaining gap.**

---

### Page 6: Hybrid Connectivity & WAN Assessment · ⚠️ ~85% Complete

| Required Content | Status | Gap |
|---|---|---|
| VPN Gateway inventory (SKU, generation, active-active) | ✅ Complete | — |
| VPN connections (IPsec, BGP, DPD timeout) | ✅ Complete | — |
| BGP health (peer state, routes learned/advertised) | ✅ Complete | — |
| ExpressRoute redundancy and peering types | ✅ Complete | — |
| ER circuit utilization (actual throughput vs provisioned) | ❌ Not collected | ❌ `PrimaryBitsInPerSecond` / `SecondaryBitsInPerSecond` monitor metrics not yet queried |
| Virtual WAN hub routing | ✅ Complete | — |

**Verdict: ⚠️ Page 6 is 85% complete. ER utilization metrics are the single missing piece.**

---

### Page 7: Observability & Monitoring Posture · ✅ ~90% Complete

| Required Content | Status | Gap |
|---|---|---|
| Network Watcher deployment (per region) | ✅ Complete | — |
| NSG flow log coverage (enabled/total) | ✅ Complete | — |
| Traffic Analytics state per flow log | ✅ AZ-NET-014 | — |
| Log Analytics workspace inventory (retention, SKU) | ✅ Complete | — |
| Gateway diagnostics enrollment | ✅ Complete | — |
| Bastion session logging | ✅ AZ-NET-015 | — |
| Firewall diagnostic logs | ✅ AZ-NET-013 | — |
| Defender for Cloud network recommendations | ❌ Not collected | ⚠️ `Microsoft.Security/assessments/read` already in `security/module.yaml` permissions |

**Verdict: ✅ Page 7 is strong. Defender for Cloud enrichment would add depth but is not blocking.**

---

### Page 8: Compliance Mapping · ⚠️ ~80% Complete

| Framework | Coverage | Gap |
|---|---|---|
| **NIST CSF 2.0** | ✅ Mapped on every finding | ✅ Complete |
| **Azure Security Benchmark v3** | ✅ NS-1 through NS-4 | ✅ Complete |
| **CIS Microsoft Azure Foundations Benchmark v2** | ✅ Controls 6.1–6.6 | ✅ Complete |
| **Azure CAF Landing Zone** | ✅ Referenced in presentation dashboard | ✅ Complete |
| **PCI-DSS 4.0** | ✅ Req 1.2, 1.3 mapped to AZ-NET-001/002/003/004/007 | ✅ Complete |
| **ISO 27001:2022 A.8.20–A.8.23** | ✅ Mapped to AZ-NET-001/002/003/004/007 | ✅ Complete |
| **HIPAA § 164.312 (technical safeguards)** | ❌ Not mapped | ❌ Healthcare clients require this |
| **FedRAMP Moderate (AC-17, SC-7, SI-4)** | ❌ Not mapped | ❌ Federal / DoD customers need this |
| **Zero Trust Network Access (CISA ZTMM v2)** | ⚠️ In `security/module.yaml` only | ⚠️ Not mapped to individual findings |

**Verdict: ⚠️ Page 8 covers all Azure-native frameworks plus PCI-DSS and ISO 27001. HIPAA and FedRAMP are additive-only — no new rules required, just `FrameworkMapping` entries.**

---

### Page 9: Findings & Risk Register · ✅ ~95% Complete

| Required Content | Status |
|---|---|
| Severity-graded finding table | ✅ Full `FindingsReport` with CRITICAL/HIGH/MEDIUM/LOW |
| Evidence references (observed state) | ✅ DD-002 enforced — every finding has `observed_state.fact` + `evidence_ref` |
| Per-finding framework control mapping | ✅ `framework_mappings` on every finding |
| Deduplication (unique issue groups) | ✅ Implemented in web UI and dedup engine |
| MS Learn doc enrichment | ✅ Live fetch at generation time |
| Finding count coverage | ✅ 13 active Azure rules (AZ-NET-001 through AZ-NET-015, excl. 005/006) |

**Current Azure rules active: 13. AZ-NET-005 and AZ-NET-006 are declared but have no emission logic (Phase C backlog).**

**Verdict: ✅ Page 9 is production-quality. Evidence-bound, framework-mapped, 13 Azure rules.**

---

### Page 10: Remediation Roadmap · ✅ Complete

| Required Content | Status |
|---|---|
| Phase 1/2/3 remediation grouping | ✅ `REMEDIATION_PLAN` deliverable + presentation dashboard |
| Effort/impact matrix | ✅ AI generates from findings |
| Azure CLI / Terraform snippets per finding | ✅ AI generates remediation code |
| Ownership assignment (subscription, resource group) | ✅ Every finding has `resource_id` → parseable to RG |
| Cost impact of remediation | ⚠️ AI can estimate; Cost Management API would enrich DDoS Standard pricing context |

---

## Part 4 — Overall Assessment Completeness Score

| Assessment Pillar | Before (2026-04-17 initial) | Now (commit `1907596`) | Remaining Blockers |
| --- | --- | --- | --- |
| **North-South** | 🟡 70% | 🟢 90% | DDoS telemetry, Front Door WAF |
| **East-West** | 🔴 45% | 🟡 65% | NSG flow log analytics (NTA bytes) — only gap |
| **Network Segmentation** | 🟡 75% | 🟢 95% | PE DNS resolution validation (nice-to-have) |
| **Hybrid / WAN** | 🟢 85% | 🟢 85% | ER utilization metrics (`PrimaryBitsInPerSecond`) |
| **Observability** | 🟡 60% | 🟢 90% | Defender for Cloud recommendations |
| **Compliance Mapping** | 🟡 65% | 🟢 80% | HIPAA § 164.312, FedRAMP Moderate |
| **Findings Quality** | 🟢 90% | 🟢 95% | AZ-NET-005/006 emission logic (Phase C) |
| **Deployment Repeatability** | 🟡 70% | 🟢 85% | node:20-alpine SHA pin, prod/dev diff |

**Overall: ~85% ready for a defensible 10-page senior architect assessment.**
*(Was ~71% before Sprint 1/2 work.)*

---

## Part 5 — Remaining Open Items (Ordered by Impact)

### Must-Have Before First Paid Client

1. **NSG flow log analytics query (east-west bytes)**
   Log Analytics `AzureNetworkAnalytics_CL` query added to `_collect_network_metrics()`.
   This is the single biggest remaining gap — Pages 3 and 7 are config-only without it.

2. **ER circuit utilization (`PrimaryBitsInPerSecond` / `SecondaryBitsInPerSecond`)**
   Azure Monitor query on ER circuit resource. Required to write capacity findings on Page 6.

3. **Cost Management API call** (`NetworkMetrics.egress_cost_usd_mtd`)
   `azure-mgmt-costmanagement` — works with Billing Reader. Schema field exists.
   Provides east-west throughput proxy without needing Azure Monitor permissions.

### High Value, Low Effort

1. **HIPAA § 164.312 and FedRAMP Moderate `framework_mappings`**
   Additive to existing rules — no new rules required. Unlocks healthcare and federal clients.

2. **Front Door WAF policy discovery**
   Single API call: `Microsoft.Network/frontDoorWebApplicationFirewallPolicies/read`.
   Closes the only gap in Page 5.

3. **DDoS attack telemetry** (`IfUnderDDoSAttack`, `DdosPacketsDropped`)
   Azure Monitor on Public IP resources. Adds attack history to Page 2.

### Production Hardening

1. **Pin `node:20-alpine` to SHA digest** in `cna-web/Dockerfile`
   `docker pull node:20-alpine --platform linux/amd64` to get digest.

2. **Verify `infra/terraform/environments/azure/prod/` mirrors `dev/`**
   `diff infra/terraform/environments/azure/dev/ infra/terraform/environments/azure/prod/`

### Phase C Backlog

1. **Implement AZ-NET-005 and AZ-NET-006 emission logic**
   Rule IDs are declared and in severity sets — no findings emitted.
   AZ-NET-005: peering `allow_gateway_transit` without explicit hub policy.
   AZ-NET-006: VNet with no flow logs enabled at all.

2. **PE DNS resolution validation**
   Network Watcher Connectivity check API — confirms PE DNS resolves to RFC 1918.

---

## Summary for a Senior Architect Conversation

**What you CAN write today (confidently, evidence-bound):**

- Full hybrid connectivity assessment (BGP, ER, VPN — excellent)
- Network segmentation posture (NSG coverage, SubnetType, peering bypass, private endpoints)
- North-south control points (Firewall — config + metrics, WAF, DDoS, NVA detection)
- Observability posture (flow logs, Traffic Analytics, Bastion/Firewall diagnostics)
- Compliance mapping: Azure WAF + NIST CSF + CIS Azure + PCI-DSS 4.0 + ISO 27001:2022

**What you CANNOT write today (data still missing):**

- East-west traffic volumes (NSG flow log analytics / NTA data)
- ER circuit saturation (requires `PrimaryBitsInPerSecond` monitor metric)
- DDoS attack history (requires `IfUnderDDoSAttack` on Public IPs)

**The single biggest remaining gap** is east-west traffic telemetry.
The NSG flow log analytics query (NTA data) is the one item that would move
Page 3 from "config analysis only" to "evidence-bound traffic assessment."
All other gaps are either already closed or are nice-to-haves.
