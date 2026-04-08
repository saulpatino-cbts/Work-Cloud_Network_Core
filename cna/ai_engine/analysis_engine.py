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
from cna.core.escalation_engine import EscalationEngine
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
}


def _severity(rule_id: str) -> FindingSeverity:
    if rule_id in _CRITICAL_IDS:
        return FindingSeverity.CRITICAL
    if rule_id in _HIGH_IDS:
        return FindingSeverity.HIGH
    return FindingSeverity.MEDIUM


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
        self._escalation = EscalationEngine()
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
                            )
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
                        )
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
                            )
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
