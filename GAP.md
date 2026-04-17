# CNA Beta Readiness · Missing Metrics · 10-Page Assessment Gap Analysis

> **Audience:** Saul Patino Jr. — AWS SA Professional | Azure Solutions Architect Expert  
> **Date:** 2026-04-17  
> **Scope:** MVP-Cloud_Network_Assessment @ `main`  
> **Persona applied:** Senior Network Architect using CNA to produce a client-deliverable 10-page assessment

---

## Part 1 — Repeatable Deployment: What Needs to Change

### 1.1 Confirmed Working ✅

The deployment sequence (000 → 010 → 030 → 031) is sound. The Terraform state isolation (separate `rg-cna-tfstate`) is properly designed. The two-pass 031 pattern (first run to get Front Door hostname, second to inject `CNA_NEXTAUTH_URL`) is documented correctly in README and TODO.

### 1.2 Gaps That Will Break a Clean Redeploy

| # | Issue | Risk | Fix |
|---|---|---|---|
| 1 | **`azure_network.py` and `azure_security.py` are stubs** (`176 bytes` and `237 bytes` respectively) | Discovery module import will succeed but produce no data — analyst will get topology JSON but zero NSG rules, route tables etc. from the module-level callers | Either wire through to `azure_discovery.py` entrypoints or add `NotImplementedError` with a clear user-facing message |
| 2 | **`MCP_SERVER_URL` not in secret/variable tables** | `module.yaml` on every module references MCP endpoints; `TODO.md` lists "MCP server wiring" as Low priority — but if any code path tries to call an MCP endpoint at runtime, it will throw without a configured URL | Add `CNA_MCP_SERVER_URL` to secrets-reference.md and `.env.example` now, even if set to `none` |
| 3 | **Node.js Dockerfile base image not SHA-pinned** (`cna-web`) | Supply-chain pinning is enforced for GitHub Actions but not for the web container — breaks supply-chain compliance posture on every redeploy that pulls a new `node:20-alpine` digest | Pin: `node:20-alpine@sha256:<hash>` — run `docker pull node:20-alpine --platform linux/amd64` and capture |
| 4 | **`KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME` reset to `none` pre-deploy** | If workflow 011 runs before 031 outputs are captured and variables updated, sync fails silently | Add a step to `031-deploy-azure.yml` that automatically writes `KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME` to GitHub Variables via the GitHub API after Terraform apply — removes the manual step |
| 5 | **`gitleaks-action` pinned to `v2` tag, not SHA** | TODO comment exists — `v2` is a mutable tag; a compromised release would run in your CI silently | Pin to exact SHA: check current `v2` SHA from `gitleaks/gitleaks-action` releases |
| 6 | **Private Endpoint IP resolution is empty** | `_collect_private_endpoints()` has a `pass` where NIC IPs should be resolved (line ~900 in `azure_discovery.py`) — every PE returns `private_ip_addresses=[]` | Implement the NIC GET: `net.network_interfaces.get(nic_rg, nic_name)` and extract `ip_configurations[*].private_ip_address` |
| 7 | **`vpn_client_pools` accumulation bug** | Line 809: `vpn_client_pools.append(pool.address_prefixes or [])` — this pushes a `list` into a `list`, creating a list-of-lists. Should be `vpn_client_pools.extend(pool.address_prefixes or [])` | One-line fix in `_collect_vnet_gateways()` |
| 8 | **Terraform `prod` environment parity** | README says "redeploy clean" but `infra/terraform/environments/azure/prod/` exists — verify it mirrors `dev/` exactly before first prod promote | Run `diff infra/terraform/environments/azure/dev/ infra/terraform/environments/azure/prod/` |

### 1.3 Deployment Hardening Recommendations

```bash
# After workflow 031 apply succeeds, auto-update GitHub Variables:
# Add this step to 031-deploy-azure.yml after terraform apply:

- name: Update GitHub Variables from Terraform outputs
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    KV_NAME: ${{ steps.tf.outputs.key_vault_name }}
    AI_NAME: ${{ steps.tf.outputs.application_insights_name }}
  run: |
    gh variable set KEY_VAULT_NAME --body "$KV_NAME"
    gh variable set APPLICATION_INSIGHTS_NAME --body "$AI_NAME"
```

---

## Part 2 — Missing Networking Metrics (Think Out-of-the-Box)

### 2.1 What You Have Today

| Metric | Source | Status |
|---|---|---|
| Gateway ingress/egress bytes (24h) | Azure Monitor – `TunnelIngressBytes`, `TunnelEgressBytes` | ✅ Collected (capped at 5 gateways) |
| NSG flow log enable/disable state | Network Watcher API | ✅ Collected |
| BGP peer state + route counts | VPN Gateway API | ✅ Collected |
| ER circuit bandwidth (provisioned) | ARM property `bandwidth_in_mbps` | ✅ Collected |
| ER gateway connection bytes (cumulative) | `AzureGatewayConnection.egress_bytes_transferred` | ✅ Collected |

### 2.2 Missing Metrics — Add These

#### 🔴 Tier 1: Critical for Assessment Completeness

| Metric | API / Source | Why It Matters for Assessment |
|---|---|---|
| **Gateway throughput utilization %** | Azure Monitor: `AverageBandwidth` (Mbps) vs SKU bandwidth ceiling | Tells you if VPN/ER is saturated. Without it, you cannot write a north-south capacity finding. Currently `GatewayMetric.utilization_pct` field exists in schema but is **never populated**. |
| **Firewall throughput + rule hit counts** | Azure Monitor: `AzureFirewall/DataProcessed`, `AzureFirewall/ApplicationRuleHit`, `AzureFirewall/NetworkRuleHit` | Required to assess whether Firewall SKU is right-sized and whether rules are actively enforced or dead letter. |
| **Load Balancer SNAT port exhaustion** | Azure Monitor: `SnatConnectionCount`, `AllocatedSnatPorts`, `UsedSnatPorts` | East-west NAT hairpin and SNAT exhaustion is one of the most common operational failures. Cannot diagnose it without these. |
| **NSG flow log traffic volume** | Azure Monitor Log Analytics query: `AzureNetworkAnalytics_CL | summarize by FlowType_s` | Needed for east-west vs north-south traffic ratio — your most valuable insight. |
| **DDoS attack telemetry** | Azure Monitor: `IfUnderDDoSAttack`, `DdosPacketsDropped` (Public IP resource) | Required for compliance sections referencing NIST IR.RP and DDoS resilience. |

#### 🟡 Tier 2: High Value, Out-of-the-Box Sources

| Metric | API / Source | Notes |
|---|---|---|
| **Azure Cost Management — network egress spend** | `/providers/Microsoft.CostManagement/query` (REST) or `azure-mgmt-costmanagement` | **Ingenious finding source:** high egress cost is a direct proxy for north-south throughput and potential data exfiltration. No other config-only tool gives you this. Map `Microsoft.Network` meter category to derive estimated Gbps/month. |
| **ExpressRoute circuit utilization (PrimaryBitsInPerSecond / SecondaryBitsInPerSecond)** | Azure Monitor on ER circuit resource | Standard ER redundancy check tells you *if* a second circuit exists. This tells you *if* the second circuit is actually carrying traffic (asymmetric routing detection). |
| **Application Gateway capacity units + latency** | Azure Monitor: `CapacityUnits`, `BackendLastByteResponseTime` | WAF is only meaningful if it's not overloaded. Latency spike = WAF OWASP rules causing performance degradation — key finding for WAF mode recommendation. |
| **Private Endpoint DNS resolution validation** | Network Watcher `checkDnsNameAvailability` or Connectivity check API | Confirms private endpoint DNS is actually resolving to RFC 1918 space — not just configured, but working. Required for zero-trust finding on PE bypass risk. |
| **VNet address space utilization %** | Calculated from `address_space` vs allocated subnets | How full is the IP space? Required for capacity planning section. Formula: sum(subnet CIDRs) / VNet CIDR × 100. Already have the data — just not computing it. |
| **Peering asymmetry** | Cross-reference `VNetPeering.allow_forwarded_traffic` + `allow_gateway_transit` + route table next-hops | Computed finding: detects hub-spoke topologies where a spoke can reach the internet directly (bypassing hub firewall) because its route table has a more-specific route. |
| **Bastion session audit availability** | Azure Monitor: `microsoft.network/bastionHosts` diagnostic logs | Bastion without session logs defeats the purpose — need to confirm Log Analytics integration, not just Bastion existence. |

#### 🟢 Tier 3: Billing-Derived (Your Original Idea — Very Smart)

The Cost Management API gives you **actual network meter data** without needing Azure Monitor permissions:

```python
# Add to _collect_network_metrics() as a fallback if Monitor 403s

from azure.mgmt.costmanagement import CostManagementClient
from datetime import datetime, timedelta

cost_client = CostManagementClient(credential)
scope = f"/subscriptions/{sub_id}"
result = cost_client.query.usage(scope, {
    "type": "ActualCost",
    "timeframe": "MonthToDate",
    "dataset": {
        "granularity": "None",
        "filter": {
            "dimensions": {
                "name": "MeterCategory",
                "operator": "In",
                "values": ["Networking"]
            }
        },
        "grouping": [{"type": "Dimension", "name": "MeterName"}]
    }
})
# MeterName values like "Inter-VNet Data Transfer", "ExpressRoute Data",
# "LB Data Processed", "VPN Gateway Bandwidth" give you throughput proxies
```

**Permission needed:** `Microsoft.CostManagement/query/action` (Reader on subscription usually sufficient)

### 2.3 Schema Changes Required

Add the following to `NetworkMetrics` in `topology_schema.py`:

```python
class FirewallMetric(BaseModel):
    firewall_name: str
    data_processed_gb_24h: float | None = None
    app_rule_hits_24h: int | None = None
    network_rule_hits_24h: int | None = None
    nat_rule_hits_24h: int | None = None

class LoadBalancerMetric(BaseModel):
    lb_name: str
    snat_connections_24h: float | None = None
    snat_port_utilization_pct: float | None = None  # UsedSnatPorts / AllocatedSnatPorts

class NetworkMetrics(BaseModel):
    gateway_metrics: list[GatewayMetric] = Field(default_factory=list)
    firewall_metrics: list[FirewallMetric] = Field(default_factory=list)      # NEW
    lb_metrics: list[LoadBalancerMetric] = Field(default_factory=list)        # NEW
    vnet_utilization: dict[str, float] = Field(default_factory=dict)         # NEW vnet_id -> pct
    egress_cost_usd_mtd: float | None = None                                  # NEW billing-derived
    collection_error: str | None = None
```

And add new analysis rules:

```python
# In analysis_engine.py — these rules write themselves once data is collected:

R_AZ_GW_HIGH_UTILIZATION    = "AZ-NET-008"  # utilization_pct > 80%
R_AZ_FW_ZERO_RULE_HITS      = "AZ-NET-009"  # firewall exists, 0 rule hits — misconfigured or unused
R_AZ_LB_SNAT_EXHAUSTION     = "AZ-NET-010"  # snat_port_utilization > 80%
R_AZ_VNET_IP_SPACE_FULL     = "AZ-NET-011"  # vnet_utilization > 85%
R_AZ_PEERING_FIREWALL_BYPASS = "AZ-NET-012" # spoke route table bypasses hub NVA/firewall
R_AZ_BASTION_NO_DIAGNOSTICS = "AZ-NET-013"  # bastion present, no LA workspace integration
```

---

## Part 3 — Senior Architect's 10-Page Assessment: Data Sufficiency Audit

> **Persona:** Senior Network Architect, 15+ years. I have been handed a CNA-generated topology JSON and FindingsReport for a client with 2 Azure subscriptions, 8 VNets, 40 subnets, 3 VPN gateways, 1 ExpressRoute circuit, 1 Azure Firewall Premium, 2 App Gateways with WAF, 15 NSGs, 30+ private endpoints, and 1 Virtual WAN.

### Page 1: Executive Summary

| Required Content | Data Available? | Gap |
|---|---|---|
| Risk score with scoring rationale | ✅ Derived from findings severity counts | ✅ Complete |
| Organization overview (subscriptions, VNets, locations) | ✅ `AzureTopology.subscriptions[*]` | ✅ Complete |
| Critical findings summary | ✅ `FindingsReport.critical_count` + `CRITICAL` findings | ✅ Complete |
| Business impact statement | ✅ AI generates from topology context | ✅ Complete |
| Assessment scope and methodology | ✅ Hardcoded section in report engine | ✅ Complete |

**Verdict: ✅ Page 1 is fully supportable today.**

---

### Page 2: Network Topology Overview (North-South)

| Required Content | Data Available? | Gap |
|---|---|---|
| Internet ingress paths (Front Door, App GW, Public IPs) | ✅ `public_ips`, `application_gateways`, DNS labels | ✅ Complete |
| Egress paths (NAT GW, Azure Firewall, public IPs on NICs) | ✅ `nat_gateways`, `firewalls`, subnet `default_outbound_access` | ✅ Complete |
| WAN connectivity (VPN connections, ER circuits) | ✅ `virtual_network_gateways`, `express_route_circuits` | ✅ Complete |
| Hybrid connectivity map (on-prem reachability) | ✅ Gateway connections + BGP learned routes | ✅ Complete |
| **Traffic volume / throughput actuals** | ⚠️ Gateway bytes only (24h total, not average) | ❌ **Missing: `AverageBandwidth` metric. Cannot write "north-south throughput averages X Gbps peak."** |
| Firewall rule utilization | ❌ Not collected | ❌ **Missing: Firewall rule hit counts. Cannot confirm firewall is actively filtering.** |
| DDoS events | ❌ Not collected | ⚠️ Can note DDoS protection state from `vnet.ddos_protection_enabled` but cannot show attack history |

**Verdict: ⚠️ Page 2 needs Tier 1 metrics (gateway utilization %, firewall rule hits) to be authoritative.**

---

### Page 3: East-West Traffic Analysis

| Required Content | Data Available? | Gap |
|---|---|---|
| VNet peering topology (hub-spoke vs mesh) | ✅ `VNetPeering` with `allow_forwarded_traffic`, `allow_gateway_transit`, `use_remote_gateways` | ✅ Complete |
| Spoke-to-spoke path analysis (do they go through hub firewall?) | ⚠️ Topology exists; computed analysis not yet done | ❌ **Missing: `AZ-NET-012` (peering firewall bypass) rule is not yet implemented** |
| Route table inspection (UDR forcing through NVA?) | ✅ Full `AzureRouteTable` with `AzureRouteEntry` including `next_hop_type` | ✅ Complete |
| NSG rule analysis (inter-subnet rules, lateral movement risk) | ✅ Full `NSGSecurityRule` with source/destination ASGs | ✅ Complete |
| Virtual WAN routing (vHub routing state, connected VNets) | ✅ `AzureVWan` → `AzureVHub` with `routing_state`, `connected_vnet_ids` | ✅ Complete |
| **Actual east-west byte counts** | ❌ Not collected | ❌ **Missing: NSG flow log analytics query (NTA data). Without this, east-west section is config-only — no traffic evidence.** |
| SNAT exhaustion risk (internal LBs, AKS pods) | ❌ Not collected | ❌ **Missing: LB SNAT metrics (Tier 1). East-west pod-to-pod communication failures are invisible without it.** |

**Verdict: ❌ Page 3 is the biggest gap. Config data is excellent but there is ZERO actual traffic telemetry for east-west flows. A senior architect will call this out immediately during peer review.**

---

### Page 4: Network Segmentation Analysis

| Required Content | Data Available? | Gap |
|---|---|---|
| Subnet classification (public/private/isolated) | ⚠️ Data exists (NSG presence, route table, delegation, `default_outbound_access`) but `SubnetType` enum is not being populated | ❌ **Missing: `_classify_subnet()` function that sets `SubnetType` based on NSG + routes** |
| NSG coverage (% of subnets with NSG) | ✅ `AZ-NET-002` rule fires per unprotected subnet, easily aggregatable | ✅ Complete |
| Application Security Groups usage | ✅ `source_asgs` and `destination_asgs` in `NSGSecurityRule` | ✅ Complete |
| Service Endpoint vs Private Endpoint strategy | ✅ `subnet.service_endpoints` + `private_endpoints` collection | ✅ Complete |
| Private Endpoint DNS correctness | ⚠️ DNS zone groups collected, IPs NOT collected (known bug in `_collect_private_endpoints`) | ❌ **Missing: PE IPs must be populated to confirm RFC 1918 resolution** |
| Subnet delegation analysis (AKS, ACA, PostgreSQL) | ✅ `subnet.delegation` field | ✅ Complete |
| Inter-region segmentation | ✅ Multi-subscription topology merge captures cross-region VNets | ✅ Complete |
| Management plane segmentation (Management Groups) | ✅ `ManagementGroup` tree | ✅ Complete |

**Verdict: ⚠️ Page 4 is ~75% complete. Two fixable bugs (SubnetType classification + PE IPs) block the rest.**

---

### Page 5: North-South Security Controls

| Required Content | Data Available? | Gap |
|---|---|---|
| Azure Firewall configuration (SKU, tier, threat intel) | ✅ `AzureFirewall.sku_tier`, `threat_intel_mode`, `policy_id` | ✅ Complete |
| WAF governance (App GW WAF mode, rule set version) | ✅ `ApplicationGateway.waf_mode`, `waf_rule_set_type/version` | ✅ Complete |
| Front Door WAF (platform-level) | ❌ Not collected | ⚠️ CNA deploys Front Door for its own platform — but does NOT assess Front Door WAF policy on the customer tenant. Need `Microsoft.Network/frontDoorWebApplicationFirewallPolicies/read` |
| DDoS protection standard enrollment | ✅ `VNet.ddos_protection_enabled` + `ddos_protection_plan_id` | ✅ Complete |
| Public IP exposure inventory | ✅ `AzurePublicIP` with `associated_resource_type` | ✅ Complete |
| Basic vs Standard SKU public IPs | ✅ `AzurePublicIP.sku_name` | ✅ Complete |
| SSL/TLS policy enforcement (App GW) | ✅ `ApplicationGateway.ssl_policy_name` | ✅ Complete |
| NVA / 3rd-party NGFW presence | ✅ `AzureNVA` with vendor identification | ✅ Complete |

**Verdict: ✅ Page 5 is strong. Add Front Door WAF collection for completeness.**

---

### Page 6: Hybrid Connectivity & WAN Assessment

| Required Content | Data Available? | Gap |
|---|---|---|
| VPN Gateway inventory (SKU, generation, active-active) | ✅ `AzureVirtualNetworkGateway` with all fields | ✅ Complete |
| VPN connections (IPsec, BGP, DPD timeout) | ✅ `AzureGatewayConnection` with all fields | ✅ Complete |
| BGP health (peer state, routes learned/advertised) | ✅ `GatewayBgpData` with full peer + route data | ✅ Complete |
| ExpressRoute redundancy and peering types | ✅ `ExpressRouteCircuit` with `peering_types`, SKU | ✅ Complete |
| ER circuit utilization (actual throughput vs provisioned) | ❌ Not collected | ❌ **Missing: ER Monitor metrics (`PrimaryBitsInPerSecond`). Cannot confirm 1Gbps circuit isn't saturated.** |
| Virtual WAN hub routing | ✅ `AzureVHub.routing_state`, connected VNets/VPN sites | ✅ Complete |
| SD-WAN / branch connectivity | ⚠️ VPN site IDs in vHub captured, but no SD-WAN-specific APIs called | ⚠️ Acceptable gap — SD-WAN is carrier-managed |

**Verdict: ⚠️ Page 6 is 90% complete. ER utilization metrics are the missing piece for a fully defensible hybrid assessment.**

---

### Page 7: Observability & Monitoring Posture

| Required Content | Data Available? | Gap |
|---|---|---|
| Network Watcher deployment (per region) | ✅ `ObservabilityData.network_watchers` | ✅ Complete |
| NSG flow log coverage (enabled/total) | ✅ `ObservabilityData.nsg_flow_logs_enabled / nsg_flow_logs_total` | ✅ Complete |
| Log Analytics workspace inventory (retention, SKU) | ✅ `LogAnalyticsWorkspace` with `retention_days` | ✅ Complete |
| Gateway diagnostics enrollment | ✅ `ObservabilityData.gateways_with_diagnostics` | ✅ Complete |
| **Traffic Analytics enabled?** | ❌ Not collected | ❌ **Missing: `TrafficAnalyticsConfiguration` on flow logs. Knowing NSG flow logs are enabled is half the story — knowing they're feeding Traffic Analytics is the other half.** |
| Bastion session logging | ❌ Not collected | ❌ **Missing: Bastion diagnostic settings query** |
| Firewall diagnostic logs | ❌ Not collected | ❌ **Missing: `AzureFirewallApplicationRule`, `AzureFirewallNetworkRule` diagnostic settings** |
| Defender for Cloud network recommendations | ❌ Not collected | ⚠️ Would require `Microsoft.Security/assessments/read` (already in `security/module.yaml` permissions) |

**Verdict: ⚠️ Page 7 is ~60% complete. Traffic Analytics state and Bastion/Firewall diagnostic settings are gaps that a compliance auditor will flag.**

---

### Page 8: Compliance Mapping

| Framework | Coverage | Gap |
|---|---|---|
| **NIST CSF 2.0** | ✅ Mapped in `framework_mappings` on every finding | ✅ Complete |
| **Azure Security Benchmark v3** | ✅ Mapped to NS-1 through NS-4 controls | ✅ Complete |
| **CIS Microsoft Azure Foundations Benchmark v2** | ✅ Controls 6.1–6.6 covered by existing rules | ✅ Complete |
| **Azure CAF Landing Zone** | ✅ Referenced in presentation dashboard | ✅ Complete |
| **PCI-DSS 4.0 (network controls)** | ❌ Not mapped | ❌ **Missing: Req 1.2 (network segmentation), Req 1.3 (restrict inbound/outbound), Req 7 (access control). High-value for financial services clients.** |
| **HIPAA § 164.312 (technical safeguards)** | ❌ Not mapped | ❌ **Missing: Healthcare clients will require this** |
| **ISO 27001:2022 A.8.20–A.8.23** | ❌ Not mapped | ❌ **Missing: Network security controls annex** |
| **FedRAMP Moderate (AC-17, SC-7, SI-4)** | ❌ Not mapped | ❌ **Missing: Federal / DoD customers need this** |
| **Zero Trust Network Access (CISA ZTMM v2)** | ✅ In `security/module.yaml` framework_mappings | ⚠️ References exist but not mapped to individual findings |

**Verdict: ⚠️ Page 8 compliance is strong for Azure-native frameworks. For a general-purpose assessment you need PCI-DSS and ISO 27001 mappings as optional overlays.**

---

### Page 9: Findings & Risk Register

| Required Content | Data Available? | Gap |
|---|---|---|
| Severity-graded finding table | ✅ Full `FindingsReport` with CRITICAL/HIGH/MEDIUM/LOW | ✅ Complete |
| Evidence references (observed state) | ✅ DD-002 enforced — every finding has `observed_state.fact` + `evidence_ref` | ✅ Complete |
| Per-finding framework control mapping | ✅ `framework_mappings` on every finding | ✅ Complete |
| Deduplication (unique issue groups) | ✅ Implemented in web UI and dedup engine | ✅ Complete |
| MS Learn doc enrichment | ✅ Live fetch at generation time | ✅ Complete |
| **Finding count coverage** | ⚠️ 18 rules total (11 AWS + 7 Azure) | ❌ **7 Azure rules is thin for a paid assessment. See Section 3.10 for the 6 missing rules already in schema.** |

**Current Azure rules coverage by domain:**

| Domain | Rules | Missing |
|---|---|---|
| North-South (DDoS, WAF, Firewall) | AZ-NET-001, 003, 007 | Firewall bypass, Front Door WAF |
| Segmentation (NSGs, subnets) | AZ-NET-002 | Subnet classification, peering bypass |
| Observability (flow logs) | AZ-NET-006 | Traffic Analytics, Bastion logs |
| Hybrid (ER redundancy) | AZ-NET-004, 005 | ER utilization, VPN SKU adequacy |

**Verdict: ⚠️ Page 9 quality is excellent (evidence-bound, framework-mapped) but quantity is thin. Need the 6 new rules from schema additions above.**

---

### Page 10: Remediation Roadmap

| Required Content | Data Available? | Gap |
|---|---|---|
| Phase 1/2/3 remediation grouping | ✅ `REMEDIATION_PLAN` deliverable + presentation dashboard | ✅ Complete |
| Effort/impact matrix | ✅ AI generates from findings | ✅ Complete |
| Azure CLI / Terraform snippets per finding | ✅ AI generates remediation code | ✅ Complete |
| Ownership assignment (subscription, resource group) | ✅ Every finding has `resource_id` → parseable to RG | ✅ Complete |
| Cost impact of remediation | ⚠️ AI can estimate but no billing data enrichment | ⚠️ Add Cost Management data for DDoS Standard pricing context |

**Verdict: ✅ Page 10 is complete.**

---

## Part 4 — Overall Assessment Completeness Score

| Assessment Pillar | Readiness | Blockers |
|---|---|---|
| **North-South** | 🟡 70% | Firewall rule hits, gateway throughput utilization, Front Door WAF |
| **East-West** | 🔴 45% | No traffic telemetry. NSG/route config is excellent but zero flow evidence |
| **Network Segmentation** | 🟡 75% | SubnetType classification function missing, PE IPs empty |
| **Hybrid / WAN** | 🟢 85% | ER utilization metrics only gap |
| **Observability** | 🟡 60% | Traffic Analytics state, Bastion/Firewall diagnostics |
| **Compliance Mapping** | 🟡 65% | PCI-DSS, ISO 27001, FedRAMP not mapped |
| **Findings Quality** | 🟢 90% | 7 Azure rules is thin — needs 6 more |
| **Deployment Repeatability** | 🟡 70% | 8 gaps listed in Part 1 |

**Overall: ~71% ready for a defensible 10-page senior architect assessment.**

---

## Part 5 — Priority Action List (Ordered by Impact)

### Do Before Beta Validation (blocks clean assessment)

1. **Fix PE IP collection** — 30-min fix in `_collect_private_endpoints()`
2. **Fix `vpn_client_pools` extend bug** — 1-line fix
3. **Implement `_classify_subnet()`** — sets `SubnetType` enum based on NSG + routes + delegation
4. **Implement peering firewall bypass check (`AZ-NET-012`)** — cross-ref spoke peerings vs hub route tables
5. **Add firewall diagnostic settings check** — 1 API call per firewall resource

### Do Before First Paid Engagement

6. **Add `AverageBandwidth` metric for VPN/ER gateways** — populates `utilization_pct` already in schema
7. **Add Azure Firewall metrics** (`DataProcessed`, rule hit counts)
8. **Add Traffic Analytics state** to `ObservabilityData`
9. **Add Cost Management API call** (billing-derived throughput proxy)
10. **Add PCI-DSS 4.0 `framework_mappings`** to existing rules (no new rules required — just add mappings)

### Do Before Production Hardening

11. Pin `node:20-alpine` to SHA digest in `cna-web/Dockerfile`
12. Pin `gitleaks-action` to SHA in `020-test-codebase.yml`
13. Auto-write `KEY_VAULT_NAME` / `APPLICATION_INSIGHTS_NAME` from Terraform outputs to GitHub Variables
14. Wire `azure_network.py` stub to `azure_discovery.py` entrypoint (or explicitly raise `NotImplementedError`)

---

## Summary for a Senior Architect Conversation

**What you CAN write today (confidently, evidence-bound):**
- Full hybrid connectivity assessment (BGP, ER, VPN — this is genuinely excellent)
- Network segmentation posture (NSG coverage, subnet analysis, private endpoints)
- North-south control points (Firewall, WAF, DDoS, NVA detection)
- Compliance mapping for Azure Security Benchmark + NIST CSF + CIS Azure

**What you CANNOT write today (no data):**
- East-west traffic volumes (requires NSG flow log analytics)
- Gateway throughput utilization (requires `AverageBandwidth` metric — field exists in schema, collector missing)
- Firewall efficacy (requires rule hit count metrics)
- SNAT exhaustion risk (requires LB metrics)

**The single biggest gap** is that your east-west section will be configuration-only with zero traffic evidence. For a 10-page senior architect report, pages 3 and 7 will look thin without telemetry. The Tier 1 Azure Monitor metric additions (Day 1 of post-beta sprint) fix this completely.

The platform foundation, evidence binding (DD-002), and parallel delivery portal are all professional-grade. The gaps are metric coverage, not architecture.
