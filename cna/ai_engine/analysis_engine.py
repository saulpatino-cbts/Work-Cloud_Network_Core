"""Phase D — AI Analysis Engine.

Consumes AWSTopology and AzureTopology checkpoints from EngagementStore.
Produces a versioned FindingsReport written back to EngagementStore.

Design contracts (all enforced in code, not just docs):
  DD-002: Every finding MUST have observed_state. Hedge language blocks publication.
  DD-003: Finding generation and recommendation injection are STRICTLY separate.
          This module generates findings only. Recommendations are injected by
          recommendation_engine.py AFTER this module completes.
  DD-008: This engine reads from our data store ONLY — never touches client env.
  DD-009: FindingsReport written to store with review_complete=False. Report engine
          refuses to generate output until review_complete=True.
  DD-016: CRITICAL findings trigger EscalationEngine before analysis completes.

Finding deduplication key: f"{finding_id}:{resource_id}"
Any finding with the same key is deduplicated — the first occurrence wins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from cna.ai_engine.observed_state_enforcer import ObservedStateEnforcer
from cna.core.escalation_engine import CriticalFindingEscalationEngine
from cna.core.findings_schema import (
    FINDINGS_SCHEMA_VERSION,
    Finding,
    FindingSeverity,
    FindingsReport,
    FindingStatus,
    FrameworkMapping,
    ObservedState,
)
from cna.core.persistence import EngagementStore
from cna.core.topology_schema import (
    AWSRegionTopology,
    AWSTopology,
    AzureSubscriptionTopology,
    AzureTopology,
)

logger = logging.getLogger("cna.analysis")

# ---------------------------------------------------------------------------
# Finding rule IDs — stable across runs, used as dedup keys
# ---------------------------------------------------------------------------

# AWS
R_AWS_DEFAULT_VPC_EXISTS = "AWS-NET-001"
R_AWS_VPC_FLOW_LOGS_DISABLED = "AWS-NET-002"
R_AWS_SG_UNRESTRICTED_SSH = "AWS-NET-003"
R_AWS_SG_UNRESTRICTED_RDP = "AWS-NET-004"
R_AWS_SG_UNRESTRICTED_ALL = "AWS-NET-005"
R_AWS_TGW_DEFAULT_RT_ASSOC = "AWS-NET-006"
R_AWS_TGW_DEFAULT_RT_PROP = "AWS-NET-007"
R_AWS_DX_NO_REDUNDANCY = "AWS-NET-008"
R_AWS_NAT_SINGLE_AZ = "AWS-NET-009"
R_AWS_SUBNET_NO_NACL = "AWS-NET-010"
R_AWS_IGW_MISSING_ROUTE = "AWS-NET-011"

# Azure
R_AZ_VNET_NO_DDOS = "AZ-NET-001"
R_AZ_SUBNET_NO_NSG = "AZ-NET-002"
R_AZ_FW_THREAT_INTEL_NOT_DENY = "AZ-NET-003"
R_AZ_ER_NO_REDUNDANCY = "AZ-NET-004"
R_AZ_PEERING_ALLOW_GW_TRANSIT = "AZ-NET-005"
R_AZ_VNET_NO_FLOW_LOGS = "AZ-NET-006"
R_AZ_APPGW_WAF_DISABLED = "AZ-NET-007"
R_AZ_GW_SATURATION = "AZ-NET-008"
R_AZ_FW_NO_HITS = "AZ-NET-009"
R_AZ_LB_SNAT_EXHAUSTION = "AZ-NET-010"
R_AZ_VNET_IP_EXHAUSTION = "AZ-NET-011"
R_AZ_PEERING_FW_BYPASS = "AZ-NET-012"
R_AZ_FW_NO_DIAGNOSTICS = "AZ-NET-013"
R_AZ_TRAFFIC_ANALYTICS_MISSING = "AZ-NET-014"
R_AZ_BASTION_NO_DIAGNOSTICS = "AZ-NET-015"

# Severity thresholds
_CRITICAL_IDS = {
    R_AWS_SG_UNRESTRICTED_SSH,
    R_AWS_SG_UNRESTRICTED_RDP,
    R_AWS_SG_UNRESTRICTED_ALL,
    R_AZ_FW_THREAT_INTEL_NOT_DENY,
}
_HIGH_IDS = {
    R_AWS_VPC_FLOW_LOGS_DISABLED,
    R_AZ_SUBNET_NO_NSG,
    R_AZ_VNET_NO_FLOW_LOGS,
    R_AZ_APPGW_WAF_DISABLED,
    R_AZ_GW_SATURATION,
    R_AZ_FW_NO_HITS,
    R_AZ_LB_SNAT_EXHAUSTION,
    R_AZ_VNET_IP_EXHAUSTION,
}

_MEDIUM_IDS = {
    R_AZ_TRAFFIC_ANALYTICS_MISSING,
    R_AZ_FW_NO_DIAGNOSTICS,
    R_AZ_BASTION_NO_DIAGNOSTICS,
    R_AZ_PEERING_FW_BYPASS,
}


def _severity(rule_id: str) -> FindingSeverity:
    if rule_id in _CRITICAL_IDS:
        return FindingSeverity.CRITICAL
    if rule_id in _HIGH_IDS:
        return FindingSeverity.HIGH
    if rule_id in _MEDIUM_IDS:
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW


@dataclass
class AnalysisOptions:
    load_aws: bool = True
    load_azure: bool = True
    dry_run: bool = False  # produce findings but do not write to store
    progress_callback: callable | None = None


class AnalysisEngine:
    """Generates findings from topology checkpoints. Writes FindingsReport.

    Strictly does NOT inject recommendations — that is RecommendationEngine's job.
    """

    def __init__(self, store: EngagementStore, options: AnalysisOptions = None):
        self.store = store
        self.opts = options or AnalysisOptions()
        self._enforcer = ObservedStateEnforcer()
        self._escalation = CriticalFindingEscalationEngine()
        self._seen: set[str] = set()  # deduplication register
        self._findings: list[Finding] = []

    # ---------------------------------------------------------------- dedup

    def _dedup_key(self, rule_id: str, resource_id: str) -> str:
        return f"{rule_id}:{resource_id}"

    def _emit(self, finding: Finding) -> None:
        """Validate, deduplicate, and register a finding."""
        # 1. Enforce observed_state — blocks hedge language (DD-002)
        self._enforcer.validate(finding)  # raises ObservedStateViolation on failure

        # 2. Enforce framework_mappings (DD-002)
        if not finding.framework_mappings:
            raise ValueError(
                f"Finding {finding.rule_id} has no framework_mappings. "
                "Every finding must map to at least one framework control."
            )

        # 3. Deduplication
        key = self._dedup_key(finding.rule_id, finding.resource_id)
        if key in self._seen:
            logger.debug("Deduplicated finding %s", key)
            return
        self._seen.add(key)

        # 4. CRITICAL escalation check (DD-016)
        if finding.severity == FindingSeverity.CRITICAL:
            self._escalation.flag(finding)

        self._findings.append(finding)
        logger.debug(
            "Finding emitted: %s on %s [%s]",
            finding.rule_id,
            finding.resource_id,
            finding.severity.value,
        )

    # ---------------------------------------------------------------- AWS rules

    def _analyze_aws_region(self, region_topo: AWSRegionTopology) -> None:
        if region_topo.discovery_blocked:
            return

        account_id = region_topo.account_id
        region = region_topo.region

        for vpc in region_topo.vpcs:
            # AWS-NET-001: Default VPC exists
            if vpc.is_default:
                self._emit(
                    Finding(
                        rule_id=R_AWS_DEFAULT_VPC_EXISTS,
                        severity=_severity(R_AWS_DEFAULT_VPC_EXISTS),
                        resource_id=vpc.id,
                        resource_type="AWS::EC2::VPC",
                        account_id=account_id,
                        region=region,
                        title="Default VPC exists",
                        observed_state=ObservedState(
                            fact=f"Default VPC {vpc.id} exists in {account_id}/{region}.",
                            evidence_ref=f"discovery:aws_{account_id}_{region}.vpcs[id={vpc.id}].is_default",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="AWS Well-Architected Framework",
                                pillar="Security",
                                control="SEC 5 — Network Protection",
                            )
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

            # AWS-NET-002: Flow logs disabled
            if not vpc.flow_logs_enabled:
                self._emit(
                    Finding(
                        rule_id=R_AWS_VPC_FLOW_LOGS_DISABLED,
                        severity=_severity(R_AWS_VPC_FLOW_LOGS_DISABLED),
                        resource_id=vpc.id,
                        resource_type="AWS::EC2::VPC",
                        account_id=account_id,
                        region=region,
                        title="VPC flow logs disabled",
                        observed_state=ObservedState(
                            fact=f"VPC {vpc.id} ({vpc.name or 'unnamed'}) has no flow logs enabled.",
                            evidence_ref=f"discovery:aws_{account_id}_{region}.vpcs[id={vpc.id}].flow_logs_enabled",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="AWS Well-Architected Framework",
                                pillar="Security",
                                control="SEC 4 — Detective Controls",
                            ),
                            FrameworkMapping(
                                framework="NIST CSF",
                                pillar="Detect",
                                control="DE.CM-1",
                            ),
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

            # AWS-NET-003/004/005: Security group unrestricted access
            for sg in vpc.security_groups:
                for rule in sg.rules:
                    if rule.direction != "ingress":
                        continue
                    for cidr in rule.cidr_ranges or []:
                        if cidr not in ("0.0.0.0/0", "::/0"):
                            continue
                        fp = rule.from_port
                        tp = rule.to_port
                        proto = rule.protocol

                        # All traffic
                        if proto == "-1":
                            self._emit(
                                Finding(
                                    rule_id=R_AWS_SG_UNRESTRICTED_ALL,
                                    severity=FindingSeverity.CRITICAL,
                                    resource_id=sg.id,
                                    resource_type="AWS::EC2::SecurityGroup",
                                    account_id=account_id,
                                    region=region,
                                    title="Security group allows all inbound traffic from internet",
                                    observed_state=ObservedState(
                                        fact=f"Security group {sg.id} ({sg.name}) in VPC {vpc.id} "
                                        f"has an ingress rule allowing all protocols from {cidr}.",
                                        evidence_ref=f"discovery:aws_{account_id}_{region}.vpcs[id={vpc.id}]"
                                        f".security_groups[id={sg.id}].rules",
                                    ),
                                    framework_mappings=[
                                        FrameworkMapping(
                                            framework="AWS Well-Architected Framework",
                                            pillar="Security",
                                            control="SEC 5 — Network Protection",
                                        ),
                                        FrameworkMapping(
                                            framework="CIS AWS Foundations Benchmark",
                                            pillar="Networking",
                                            control="4.1",
                                        ),
                                    ],
                                    status=FindingStatus.OPEN,
                                )
                            )
                            continue

                        # SSH
                        if proto in ("tcp", "6") and fp is not None and fp <= 22 <= (tp or fp):
                            self._emit(
                                Finding(
                                    rule_id=R_AWS_SG_UNRESTRICTED_SSH,
                                    severity=FindingSeverity.CRITICAL,
                                    resource_id=sg.id,
                                    resource_type="AWS::EC2::SecurityGroup",
                                    account_id=account_id,
                                    region=region,
                                    title="Security group allows unrestricted SSH (port 22) from internet",
                                    observed_state=ObservedState(
                                        fact=f"Security group {sg.id} ({sg.name}) in VPC {vpc.id} "
                                        f"allows TCP port 22 from {cidr}.",
                                        evidence_ref=f"discovery:aws_{account_id}_{region}.vpcs[id={vpc.id}]"
                                        f".security_groups[id={sg.id}].rules",
                                    ),
                                    framework_mappings=[
                                        FrameworkMapping(
                                            framework="AWS Well-Architected Framework",
                                            pillar="Security",
                                            control="SEC 5 — Network Protection",
                                        ),
                                        FrameworkMapping(
                                            framework="CIS AWS Foundations Benchmark",
                                            pillar="Networking",
                                            control="4.1",
                                        ),
                                    ],
                                    status=FindingStatus.OPEN,
                                )
                            )

                        # RDP
                        if proto in ("tcp", "6") and fp is not None and fp <= 3389 <= (tp or fp):
                            self._emit(
                                Finding(
                                    rule_id=R_AWS_SG_UNRESTRICTED_RDP,
                                    severity=FindingSeverity.CRITICAL,
                                    resource_id=sg.id,
                                    resource_type="AWS::EC2::SecurityGroup",
                                    account_id=account_id,
                                    region=region,
                                    title="Security group allows unrestricted RDP (port 3389) from internet",
                                    observed_state=ObservedState(
                                        fact=f"Security group {sg.id} ({sg.name}) in VPC {vpc.id} "
                                        f"allows TCP port 3389 from {cidr}.",
                                        evidence_ref=f"discovery:aws_{account_id}_{region}.vpcs[id={vpc.id}]"
                                        f".security_groups[id={sg.id}].rules",
                                    ),
                                    framework_mappings=[
                                        FrameworkMapping(
                                            framework="AWS Well-Architected Framework",
                                            pillar="Security",
                                            control="SEC 5 — Network Protection",
                                        ),
                                        FrameworkMapping(
                                            framework="CIS AWS Foundations Benchmark",
                                            pillar="Networking",
                                            control="4.2",
                                        ),
                                    ],
                                    status=FindingStatus.OPEN,
                                )
                            )

        # TGW findings
        for tgw in region_topo.transit_gateways:
            if tgw.default_route_table_association:
                self._emit(
                    Finding(
                        rule_id=R_AWS_TGW_DEFAULT_RT_ASSOC,
                        severity=_severity(R_AWS_TGW_DEFAULT_RT_ASSOC),
                        resource_id=tgw.id,
                        resource_type="AWS::EC2::TransitGateway",
                        account_id=account_id,
                        region=region,
                        title="TGW default route table association enabled",
                        observed_state=ObservedState(
                            fact=f"Transit Gateway {tgw.id} ({tgw.name or 'unnamed'}) has "
                            f"DefaultRouteTableAssociation=enable. All new attachments "
                            f"associate to the default route table automatically.",
                            evidence_ref=f"discovery:aws_{account_id}_{region}"
                            f".transit_gateways[id={tgw.id}].default_route_table_association",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="AWS Well-Architected Framework",
                                pillar="Security",
                                control="SEC 5 — Network Protection",
                            )
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

            if tgw.default_route_table_propagation:
                self._emit(
                    Finding(
                        rule_id=R_AWS_TGW_DEFAULT_RT_PROP,
                        severity=_severity(R_AWS_TGW_DEFAULT_RT_PROP),
                        resource_id=tgw.id,
                        resource_type="AWS::EC2::TransitGateway",
                        account_id=account_id,
                        region=region,
                        title="TGW default route table propagation enabled",
                        observed_state=ObservedState(
                            fact=f"Transit Gateway {tgw.id} has DefaultRouteTablePropagation=enable. "
                            f"Routes propagate to shared route table without explicit policy.",
                            evidence_ref=f"discovery:aws_{account_id}_{region}"
                            f".transit_gateways[id={tgw.id}].default_route_table_propagation",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="AWS Well-Architected Framework",
                                pillar="Security",
                                control="SEC 5 — Network Protection",
                            )
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

        # DX redundancy
        dx_connections = region_topo.direct_connect_connections
        if len(dx_connections) == 1:
            self._emit(
                Finding(
                    rule_id=R_AWS_DX_NO_REDUNDANCY,
                    severity=_severity(R_AWS_DX_NO_REDUNDANCY),
                    resource_id=dx_connections[0].id,
                    resource_type="AWS::DirectConnect::Connection",
                    account_id=account_id,
                    region=region,
                    title="Single Direct Connect connection — no redundancy",
                    observed_state=ObservedState(
                        fact=f"Only one Direct Connect connection ({dx_connections[0].id}, "
                        f"{dx_connections[0].bandwidth}) found in {region}. "
                        f"No redundant path exists.",
                        evidence_ref=f"discovery:aws_{account_id}_{region}.direct_connect_connections",
                    ),
                    framework_mappings=[
                        FrameworkMapping(
                            framework="AWS Well-Architected Framework",
                            pillar="Reliability",
                            control="REL 6 — Design to Withstand Component Failure",
                        )
                    ],
                    status=FindingStatus.OPEN,
                )
            )

    # ---------------------------------------------------------------- Azure rules

    # Well-known infrastructure subnet names excluded from workload checks
    _INFRA_SUBNETS = frozenset({
        "gatewaysubnet",
        "azurefirewallsubnet",
        "azurefirewallmanagementsubnet",
        "azurebastionsubnet",
        "routeservicesubnet",
    })

    def _analyze_azure_subscription(self, sub_topo: AzureSubscriptionTopology) -> None:
        if sub_topo.discovery_blocked:
            return

        sub_id = sub_topo.subscription_id

        for vnet in sub_topo.vnets:
            # AZ-NET-001: No DDoS protection
            if not vnet.ddos_protection_enabled:
                self._emit(
                    Finding(
                        rule_id=R_AZ_VNET_NO_DDOS,
                        severity=_severity(R_AZ_VNET_NO_DDOS),
                        resource_id=vnet.id,
                        resource_type="Microsoft.Network/virtualNetworks",
                        account_id=sub_id,
                        region=vnet.location,
                        title="VNet does not have DDoS Protection enabled",
                        observed_state=ObservedState(
                            fact=f"VNet {vnet.name} ({vnet.id}) in {vnet.location} has "
                            f"DDoS Protection Standard disabled.",
                            evidence_ref=f"discovery:azure_{sub_id}.vnets[id={vnet.id}].ddos_protection_enabled",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="Azure Well-Architected Framework",
                                pillar="Security",
                                control="NS-1 — Establish network segmentation boundaries",
                            ),
                            FrameworkMapping(
                                framework="ISO 27001:2022",
                                pillar="Network Security",
                                control="A.8.20 — Networks security",
                            ),
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

            # AZ-NET-002: Subnets without NSG
            for subnet in vnet.subnets:
                if not subnet.nsg_id:
                    # Skip GatewaySubnet — NSG not allowed
                    if subnet.name and subnet.name.lower() == "gatewaysubnet":
                        continue
                    self._emit(
                        Finding(
                            rule_id=R_AZ_SUBNET_NO_NSG,
                            severity=_severity(R_AZ_SUBNET_NO_NSG),
                            resource_id=subnet.id,
                            resource_type="Microsoft.Network/virtualNetworks/subnets",
                            account_id=sub_id,
                            region=vnet.location,
                            title="Subnet has no Network Security Group",
                            observed_state=ObservedState(
                                fact=f"Subnet {subnet.name} ({subnet.id}) in VNet {vnet.name} "
                                f"has no NSG attached.",
                                evidence_ref=f"discovery:azure_{sub_id}.vnets[id={vnet.id}]"
                                f".subnets[id={subnet.id}].nsg_id",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Security",
                                    control="NS-1 — Establish network segmentation boundaries",
                                ),
                                FrameworkMapping(
                                    framework="CIS Microsoft Azure Foundations Benchmark",
                                    pillar="Networking",
                                    control="6.2",
                                ),
                                FrameworkMapping(
                                    framework="PCI-DSS 4.0",
                                    pillar="Network Security Controls",
                                    control="Req 1.2 — Network security controls configured "
                                    "and maintained",
                                ),
                                FrameworkMapping(
                                    framework="ISO 27001:2022",
                                    pillar="Network Security",
                                    control="A.8.22 — Segregation of networks",
                                ),
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )

        # AZ-NET-003: Azure Firewall Threat Intel not Deny
        for fw in sub_topo.firewalls:
            if fw.threat_intel_mode.lower() != "deny":
                self._emit(
                    Finding(
                        rule_id=R_AZ_FW_THREAT_INTEL_NOT_DENY,
                        severity=FindingSeverity.CRITICAL,
                        resource_id=fw.id,
                        resource_type="Microsoft.Network/azureFirewalls",
                        account_id=sub_id,
                        region=fw.location,
                        title="Azure Firewall Threat Intelligence mode is not set to Deny",
                        observed_state=ObservedState(
                            fact=f"Azure Firewall {fw.name} has ThreatIntelMode='{fw.threat_intel_mode}'. "
                            f"Known malicious IPs and domains are not actively blocked.",
                            evidence_ref=f"discovery:azure_{sub_id}.firewalls[id={fw.id}].threat_intel_mode",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="Azure Well-Architected Framework",
                                pillar="Security",
                                control="NS-4 — Protect applications from external network attacks",
                            ),
                            FrameworkMapping(
                                framework="NIST CSF",
                                pillar="Protect",
                                control="PR.PT-4",
                            ),
                            FrameworkMapping(
                                framework="PCI-DSS 4.0",
                                pillar="Network Security Controls",
                                control="Req 1.3 — Restrict inbound and outbound traffic",
                            ),
                            FrameworkMapping(
                                framework="ISO 27001:2022",
                                pillar="Network Security",
                                control="A.8.20 — Networks security",
                            ),
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

        # AZ-NET-004: ExpressRoute without redundancy
        if len(sub_topo.express_route_circuits) == 1:
            er = sub_topo.express_route_circuits[0]
            self._emit(
                Finding(
                    rule_id=R_AZ_ER_NO_REDUNDANCY,
                    severity=_severity(R_AZ_ER_NO_REDUNDANCY),
                    resource_id=er.id,
                    resource_type="Microsoft.Network/expressRouteCircuits",
                    account_id=sub_id,
                    region=er.location,
                    title="Single ExpressRoute circuit — no redundancy",
                    observed_state=ObservedState(
                        fact=f"Only one ExpressRoute circuit ({er.name}, {er.bandwidth_mbps}Mbps via "
                        f"{er.service_provider or 'unknown provider'}) found in subscription {sub_id}.",
                        evidence_ref=f"discovery:azure_{sub_id}.express_route_circuits",
                    ),
                    framework_mappings=[
                        FrameworkMapping(
                            framework="Azure Well-Architected Framework",
                            pillar="Reliability",
                            control="RE-3 — Use redundant connectivity",
                        ),
                        FrameworkMapping(
                            framework="ISO 27001:2022",
                            pillar="Network Security",
                            control="A.8.21 — Security of network services",
                        ),
                    ],
                    status=FindingStatus.OPEN,
                )
            )

        # AZ-NET-007: App Gateway WAF disabled
        for agw in sub_topo.application_gateways:
            if not agw.waf_enabled:
                self._emit(
                    Finding(
                        rule_id=R_AZ_APPGW_WAF_DISABLED,
                        severity=_severity(R_AZ_APPGW_WAF_DISABLED),
                        resource_id=agw.id,
                        resource_type="Microsoft.Network/applicationGateways",
                        account_id=sub_id,
                        region=agw.location,
                        title="Application Gateway WAF is disabled",
                        observed_state=ObservedState(
                            fact=f"Application Gateway {agw.name} ({agw.sku_name}) has "
                            f"Web Application Firewall disabled.",
                            evidence_ref=f"discovery:azure_{sub_id}.application_gateways[id={agw.id}].waf_enabled",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="Azure Well-Architected Framework",
                                pillar="Security",
                                control="NS-4 — Protect applications from external network attacks",
                            ),
                            FrameworkMapping(
                                framework="PCI-DSS 4.0",
                                pillar="Network Security Controls",
                                control="Req 1.3 — Restrict inbound and outbound traffic",
                            ),
                            FrameworkMapping(
                                framework="ISO 27001:2022",
                                pillar="Network Security",
                                control="A.8.23 — Web filtering",
                            ),
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

        # AZ-NET-008: Gateway saturation
        if sub_topo.network_metrics:
            for gm in sub_topo.network_metrics.gateway_metrics:
                if gm.utilization_pct and gm.utilization_pct > 80.0:
                    self._emit(
                        Finding(
                            rule_id=R_AZ_GW_SATURATION,
                            severity=_severity(R_AZ_GW_SATURATION),
                            resource_id=sub_id,
                            resource_type="Microsoft.Network/virtualNetworkGateways",
                            account_id=sub_id,
                            region="Global",
                            title="Virtual Network Gateway utilization exceeds 80%",
                            observed_state=ObservedState(
                                fact=f"Gateway {gm.gateway_name} has {gm.utilization_pct}% utilization.",
                                evidence_ref=f"discovery:azure_{sub_id}.network_metrics",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Performance Efficiency",
                                    control="PE-3 — Monitor and optimize network performance",
                                )
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )

            # AZ-NET-009: Firewall with 0 hits
            for fm in sub_topo.network_metrics.firewall_metrics:
                if (fm.network_rule_hits_24h == 0 and fm.app_rule_hits_24h == 0 and fm.nat_rule_hits_24h == 0) or (fm.data_processed_gb_24h == 0.0):
                    self._emit(
                        Finding(
                            rule_id=R_AZ_FW_NO_HITS,
                            severity=_severity(R_AZ_FW_NO_HITS),
                            resource_id=sub_id,
                            resource_type="Microsoft.Network/azureFirewalls",
                            account_id=sub_id,
                            region="Global",
                            title="Azure Firewall present but processes 0 traffic",
                            observed_state=ObservedState(
                                fact=f"Firewall {fm.firewall_name} recorded 0 rule hits or 0 data processed in 24 hours. "
                                "It may be misconfigured or bypassed by routing.",
                                evidence_ref=f"discovery:azure_{sub_id}.network_metrics",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Security",
                                    control="NS-4 — Protect applications from external network attacks",
                                )
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )

            # AZ-NET-010: SNAT exhaustion
            for lm in sub_topo.network_metrics.lb_metrics:
                if lm.snat_port_utilization_pct and lm.snat_port_utilization_pct > 80.0:
                    self._emit(
                        Finding(
                            rule_id=R_AZ_LB_SNAT_EXHAUSTION,
                            severity=_severity(R_AZ_LB_SNAT_EXHAUSTION),
                            resource_id=sub_id,
                            resource_type="Microsoft.Network/loadBalancers",
                            account_id=sub_id,
                            region="Global",
                            title="Load Balancer SNAT port utilization exceeds 80%",
                            observed_state=ObservedState(
                                fact=f"Load Balancer {lm.lb_name} used {lm.snat_port_utilization_pct}% of allocated SNAT ports.",
                                evidence_ref=f"discovery:azure_{sub_id}.network_metrics",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Reliability",
                                    control="RE-4 — Design for scale out",
                                )
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )

            # AZ-NET-011: VNet IP Exhaustion
            for vnet_id, util in sub_topo.network_metrics.vnet_utilization.items():
                if util > 85.0:
                    self._emit(
                        Finding(
                            rule_id=R_AZ_VNET_IP_EXHAUSTION,
                            severity=_severity(R_AZ_VNET_IP_EXHAUSTION),
                            resource_id=vnet_id,
                            resource_type="Microsoft.Network/virtualNetworks",
                            account_id=sub_id,
                            region="Global",
                            title="VNet IP space utilization exceeds 85%",
                            observed_state=ObservedState(
                                fact=f"VNet {vnet_id} has {util}% of its address space allocated to subnets.",
                                evidence_ref=f"discovery:azure_{sub_id}.network_metrics",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Reliability",
                                    control="RE-2 — Design for capacity",
                                )
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )

        # AZ-NET-014: Traffic Analytics missing
        if sub_topo.observability:
            obs = sub_topo.observability
            if obs.nsg_flow_logs_enabled > 0 and obs.traffic_analytics_enabled == 0:
                self._emit(
                    Finding(
                        rule_id=R_AZ_TRAFFIC_ANALYTICS_MISSING,
                        severity=_severity(R_AZ_TRAFFIC_ANALYTICS_MISSING),
                        resource_id=sub_id,
                        resource_type="Microsoft.Network/networkSecurityGroups",
                        account_id=sub_id,
                        region="Global",
                        title="NSG Flow Logs are enabled but Traffic Analytics is disabled",
                        observed_state=ObservedState(
                            fact=f"Subscription has {obs.nsg_flow_logs_enabled} active flow "
                            f"logs, but {obs.traffic_analytics_enabled} have Traffic "
                            f"Analytics enabled.",
                            evidence_ref=f"discovery:azure_{sub_id}.observability",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="Azure Well-Architected Framework",
                                pillar="Security",
                                control="NS-2 — Monitor network security",
                            )
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

            # AZ-NET-013: Firewall without Log Analytics diagnostic sink
            if obs.firewalls_total > 0 and obs.firewalls_with_diagnostics < obs.firewalls_total:
                missing = obs.firewalls_total - obs.firewalls_with_diagnostics
                self._emit(
                    Finding(
                        rule_id=R_AZ_FW_NO_DIAGNOSTICS,
                        severity=_severity(R_AZ_FW_NO_DIAGNOSTICS),
                        resource_id=sub_id,
                        resource_type="Microsoft.Network/azureFirewalls",
                        account_id=sub_id,
                        region="Global",
                        title="Azure Firewall lacks Log Analytics diagnostic settings",
                        observed_state=ObservedState(
                            fact=f"{missing} of {obs.firewalls_total} Azure Firewall(s) "
                            f"in subscription {sub_id} have no Log Analytics diagnostic "
                            f"sink. Firewall rule logs and threat intel logs are lost.",
                            evidence_ref=f"discovery:azure_{sub_id}.observability"
                            f".firewalls_with_diagnostics",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="Azure Well-Architected Framework",
                                pillar="Security",
                                control="NS-3 — Deploy firewall at the edge of enterprise network",
                            ),
                            FrameworkMapping(
                                framework="NIST CSF",
                                pillar="Detect",
                                control="DE.CM-1 — The network is monitored to detect potential "
                                "cybersecurity events",
                            ),
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

            # AZ-NET-015: Bastion without Log Analytics diagnostic sink
            if obs.bastion_total > 0 and obs.bastion_with_diagnostics < obs.bastion_total:
                missing = obs.bastion_total - obs.bastion_with_diagnostics
                self._emit(
                    Finding(
                        rule_id=R_AZ_BASTION_NO_DIAGNOSTICS,
                        severity=_severity(R_AZ_BASTION_NO_DIAGNOSTICS),
                        resource_id=sub_id,
                        resource_type="Microsoft.Network/bastionHosts",
                        account_id=sub_id,
                        region="Global",
                        title="Azure Bastion lacks session audit logging",
                        observed_state=ObservedState(
                            fact=f"{missing} of {obs.bastion_total} Bastion host(s) "
                            f"in subscription {sub_id} have no Log Analytics diagnostic "
                            f"sink. SSH/RDP session audit trails are unavailable.",
                            evidence_ref=f"discovery:azure_{sub_id}.observability"
                            f".bastion_with_diagnostics",
                        ),
                        framework_mappings=[
                            FrameworkMapping(
                                framework="Azure Well-Architected Framework",
                                pillar="Security",
                                control="PA-2 — Avoid standing access for user accounts and "
                                "permissions",
                            ),
                            FrameworkMapping(
                                framework="NIST CSF",
                                pillar="Detect",
                                control="DE.CM-3 — Personnel activity is monitored",
                            ),
                        ],
                        status=FindingStatus.OPEN,
                    )
                )

        # AZ-NET-012: Peering firewall bypass
        # Detect spoke VNets in a hub-spoke topology where a subnet lacks a
        # UDR forcing 0.0.0.0/0 through the hub NVA/firewall.
        rt_by_name = {rt.name: rt for rt in sub_topo.route_tables}
        for vnet in sub_topo.vnets:
            # A spoke VNet has at least one peering where the remote side
            # uses gateway transit (use_remote_gateways=True on this side)
            # or allows forwarded traffic (allow_forwarded_traffic=True).
            is_spoke = any(
                p.allow_forwarded_traffic or p.use_remote_gateways
                for p in vnet.peerings
            )
            if not is_spoke:
                continue

            for subnet in vnet.subnets:
                if subnet.name.lower() in self._INFRA_SUBNETS:
                    continue
                rt = rt_by_name.get(subnet.route_table_name or "")
                if rt is None:
                    # No UDR at all → spoke subnet with no forced routing
                    self._emit(
                        Finding(
                            rule_id=R_AZ_PEERING_FW_BYPASS,
                            severity=_severity(R_AZ_PEERING_FW_BYPASS),
                            resource_id=subnet.id,
                            resource_type="Microsoft.Network/virtualNetworks/subnets",
                            account_id=sub_id,
                            region=vnet.location,
                            title="Spoke subnet has no UDR — hub firewall may be bypassed",
                            observed_state=ObservedState(
                                fact=f"Subnet {subnet.name} in spoke VNet {vnet.name} "
                                f"has no route table. Internet-bound traffic may egress "
                                f"directly rather than through the hub NVA/firewall.",
                                evidence_ref=f"discovery:azure_{sub_id}"
                                f".vnets[id={vnet.id}].subnets[id={subnet.id}]"
                                f".route_table_name",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Security",
                                    control="NS-1 — Establish network segmentation boundaries",
                                ),
                                FrameworkMapping(
                                    framework="Azure Security Benchmark",
                                    pillar="Network Security",
                                    control="NS-4",
                                ),
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )
                    continue

                has_forced_route = any(
                    r.address_prefix == "0.0.0.0/0"
                    and r.next_hop_type == "VirtualAppliance"
                    for r in rt.routes
                )
                if not has_forced_route:
                    self._emit(
                        Finding(
                            rule_id=R_AZ_PEERING_FW_BYPASS,
                            severity=_severity(R_AZ_PEERING_FW_BYPASS),
                            resource_id=subnet.id,
                            resource_type="Microsoft.Network/virtualNetworks/subnets",
                            account_id=sub_id,
                            region=vnet.location,
                            title="Spoke subnet UDR lacks 0.0.0.0/0 → NVA route",
                            observed_state=ObservedState(
                                fact=f"Subnet {subnet.name} in spoke VNet {vnet.name} "
                                f"has route table {rt.name} but no default route "
                                f"(0.0.0.0/0) pointing to a VirtualAppliance. "
                                f"Internet traffic may bypass the hub firewall.",
                                evidence_ref=f"discovery:azure_{sub_id}"
                                f".route_tables[name={rt.name}].routes",
                            ),
                            framework_mappings=[
                                FrameworkMapping(
                                    framework="Azure Well-Architected Framework",
                                    pillar="Security",
                                    control="NS-1 — Establish network segmentation boundaries",
                                ),
                                FrameworkMapping(
                                    framework="Azure Security Benchmark",
                                    pillar="Network Security",
                                    control="NS-4",
                                ),
                            ],
                            status=FindingStatus.OPEN,
                        )
                    )

    # ---------------------------------------------------------------- run

    def run(
        self,
        aws_topology: AWSTopology | None = None,
        azure_topology: AzureTopology | None = None,
    ) -> FindingsReport:
        """Execute analysis. Returns FindingsReport.

        Call sequence:
          1. Analyze AWS regions (if aws_topology provided)
          2. Analyze Azure subscriptions (if azure_topology provided)
          3. Validate escalations (DD-016)
          4. Write FindingsReport to store (unless dry_run)
          5. Return report
        """
        engagement_id = self.store.engagement_id
        self._findings = []
        self._seen = set()

        progress = self.opts.progress_callback

        # AWS
        if aws_topology and self.opts.load_aws:
            total = len(aws_topology.regions)
            for i, region_topo in enumerate(aws_topology.regions):
                if progress:
                    progress("aws", i + 1, total, f"{region_topo.account_id}/{region_topo.region}")
                self._analyze_aws_region(region_topo)

        # Azure
        if azure_topology and self.opts.load_azure:
            total = len(azure_topology.subscriptions)
            for i, sub_topo in enumerate(azure_topology.subscriptions):
                if progress:
                    progress("azure", i + 1, total, sub_topo.subscription_id)
                self._analyze_azure_subscription(sub_topo)

        # Escalation check (DD-016)
        critical_findings = [f for f in self._findings if f.severity == FindingSeverity.CRITICAL]
        if critical_findings:
            logger.warning(
                "[%s] %d CRITICAL findings detected — escalation engine triggered",
                engagement_id,
                len(critical_findings),
            )
            self._escalation.process(engagement_id, critical_findings)

        report = FindingsReport(
            engagement_id=engagement_id,
            schema_version=FINDINGS_SCHEMA_VERSION,
            findings=self._findings,
            total_count=len(self._findings),
            critical_count=len(
                [f for f in self._findings if f.severity == FindingSeverity.CRITICAL]
            ),
            high_count=len([f for f in self._findings if f.severity == FindingSeverity.HIGH]),
            medium_count=len([f for f in self._findings if f.severity == FindingSeverity.MEDIUM]),
            low_count=len([f for f in self._findings if f.severity == FindingSeverity.LOW]),
            review_complete=False,  # DD-009: must be set to True manually
            generated_at=datetime.now(UTC).isoformat(),
        )

        if not self.opts.dry_run:
            self.store.write_findings_report(
                engagement_id,
                report.model_dump(),
            )
            logger.info(
                "[%s] FindingsReport written: %d findings (%d CRITICAL, %d HIGH, %d MEDIUM, %d LOW)",
                engagement_id,
                report.total_count,
                report.critical_count,
                report.high_count,
                report.medium_count,
                report.low_count,
            )

        return report
