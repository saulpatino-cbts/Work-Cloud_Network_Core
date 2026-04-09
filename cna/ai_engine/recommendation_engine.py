"""Phase D — Recommendation Engine (DD-003).

Strict separation contract:
  - AnalysisEngine generates findings from observed topology data.
  - THIS module injects vendor recommendations AFTER findings are generated.
  - Recommendations come from MCP servers (awslabs/mcp, Azure MCP Server).
  - Recommendations are NEVER mixed into the finding's observed_state field.
  - Recommendations are stored in Finding.recommendations[] — a separate list.

MCP fallback:
  If an MCP server is unreachable, recommendations are populated from a
  curated offline fallback library (cna/ai_engine/mcp_client/offline_library.py).
  The finding is still published — missing recommendations never block the report.
"""

from __future__ import annotations

import logging

from cna.ai_engine.mcp_client.mcp_router import MCPRouter
from cna.core.findings_schema import FindingRecommendation, FindingsReport

logger = logging.getLogger("cna.recommendation")


class RecommendationEngine:
    """Injects vendor recommendations into an existing FindingsReport.

    Contract: called AFTER AnalysisEngine.run() — never before.
    Modifies findings in-place. Returns updated report.
    """

    def __init__(self, router: MCPRouter | None = None):
        self._router = router or MCPRouter()

    def enrich(self, report: FindingsReport) -> FindingsReport:
        """Inject recommendations into all findings in a report.

        Findings are modified in-place. Report is returned for chaining.
        """
        total = len(report.findings)
        enriched = 0
        fallback = 0

        for finding in report.findings:
            try:
                rt = finding.resource_type or ""
                if rt.startswith("AWS") or rt.lower().startswith("aws/"):
                    cloud = "aws"
                elif rt.startswith("Microsoft.") or rt.lower().startswith("azure/"):
                    cloud = "azure"
                elif "/" in rt:
                    cloud = rt.split("/")[0].lower()
                else:
                    cloud = "aws"
                recs = self._router.get_recommendations(
                    cloud=cloud,
                    rule_id=finding.rule_id,
                    resource_type=finding.resource_type,
                    finding_title=finding.title,
                )
                finding.recommendations = recs
                enriched += 1
            except Exception as e:
                logger.warning(
                    "MCP recommendation fetch failed for %s on %s: %s. Using offline fallback.",
                    finding.rule_id,
                    finding.resource_id,
                    e,
                )
                finding.recommendations = self._offline_fallback(finding.rule_id)
                fallback += 1

        logger.info(
            "Recommendation enrichment complete: %d/%d from MCP, %d from offline fallback",
            enriched,
            total,
            fallback,
        )
        return report

    @staticmethod
    def _offline_fallback(rule_id: str) -> list[FindingRecommendation]:
        """Return curated offline recommendations when MCP is unavailable."""
        _library = {
            "AWS-NET-001": [
                FindingRecommendation(
                    source="AWS Well-Architected Framework",
                    text="Delete the default VPC in all regions where it is not in use. "
                    "Use custom VPCs with explicit CIDR ranges and documented purpose.",
                    reference_url="https://docs.aws.amazon.com/vpc/latest/userguide/default-vpc.html",
                )
            ],
            "AWS-NET-002": [
                FindingRecommendation(
                    source="AWS Well-Architected Framework",
                    text="Enable VPC Flow Logs to an S3 bucket or CloudWatch Logs group. "
                    "Retain logs for minimum 90 days per compliance requirements.",
                    reference_url="https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html",
                )
            ],
            "AWS-NET-003": [
                FindingRecommendation(
                    source="CIS AWS Foundations Benchmark v3.0",
                    text="Remove the 0.0.0.0/0 and ::/0 SSH ingress rules. "
                    "Replace with specific IP ranges or use AWS Systems Manager Session Manager.",
                    reference_url="https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html",
                )
            ],
            "AWS-NET-004": [
                FindingRecommendation(
                    source="CIS AWS Foundations Benchmark v3.0",
                    text="Remove the 0.0.0.0/0 and ::/0 RDP ingress rules. "
                    "Replace with specific IP ranges or use AWS Systems Manager Fleet Manager.",
                    reference_url="https://docs.aws.amazon.com/systems-manager/latest/userguide/fleet-rdp.html",
                )
            ],
            "AWS-NET-006": [
                FindingRecommendation(
                    source="AWS Well-Architected Framework",
                    text="Disable DefaultRouteTableAssociation on the TGW and create explicit "
                    "route table associations per attachment to enforce network segmentation.",
                    reference_url="https://docs.aws.amazon.com/vpc/latest/tgw/tgw-route-tables.html",
                )
            ],
            "AWS-NET-008": [
                FindingRecommendation(
                    source="AWS Well-Architected Framework",
                    text="Provision a second Direct Connect connection at a different colocation "
                    "facility or use Site-to-Site VPN as a backup path.",
                    reference_url="https://docs.aws.amazon.com/directconnect/latest/UserGuide/resilency_toolkit.html",
                )
            ],
            "AZ-NET-001": [
                FindingRecommendation(
                    source="Azure Well-Architected Framework",
                    text="Enable Azure DDoS Protection Standard on the VNet. "
                    "Associate a DDoS protection plan and configure metric alerts.",
                    reference_url="https://learn.microsoft.com/azure/ddos-protection/ddos-protection-standard-features",
                )
            ],
            "AZ-NET-002": [
                FindingRecommendation(
                    source="CIS Microsoft Azure Foundations Benchmark",
                    text="Attach an NSG to every subnet. NSGs should deny all inbound traffic "
                    "by default and allow only explicitly required flows.",
                    reference_url="https://learn.microsoft.com/azure/virtual-network/network-security-groups-overview",
                )
            ],
            "AZ-NET-003": [
                FindingRecommendation(
                    source="Azure Well-Architected Framework",
                    text="Set Azure Firewall Threat Intelligence mode to 'Deny' to block "
                    "traffic to/from known malicious IPs and FQDNs.",
                    reference_url="https://learn.microsoft.com/azure/firewall/threat-intel",
                )
            ],
            "AZ-NET-007": [
                FindingRecommendation(
                    source="Azure Well-Architected Framework",
                    text="Enable WAF on the Application Gateway using WAF_v2 SKU. "
                    "Start in Detection mode, tune false positives, then switch to Prevention.",
                    reference_url="https://learn.microsoft.com/azure/web-application-firewall/ag/ag-overview",
                )
            ],
        }
        return _library.get(
            rule_id,
            [
                FindingRecommendation(
                    source="CNA Platform",
                    text="Consult the relevant AWS or Azure Well-Architected Framework guidance "
                    "for this finding type. MCP server was unavailable during enrichment.",
                    reference_url="",
                )
            ],
        )
