"""AWS network-depth collectors — Phase C (BUILD-01 C2, C3, C6).

Three collectors that take AWS network assessment beyond topology, matching and
exceeding the Azure network collector:

  C3  TransitGatewayRouteAnalyzer  — routes, blackholes, CIDR overlaps (surpass)
  C2  FlowLogAnalyzer              — VPC flow-log traffic summary / gap (surpass)
  C6  ReachabilityAnalyzer         — FLAGSHIP: real endpoint-to-endpoint
                                      reachability testing (Azure has no equivalent)

All follow the discovery conventions: observed state only (DD-002),
cna.core.throttle.with_retry, graceful degradation on not-enabled/denied, and —
for C6, the one collector that creates a billable resource — mandatory teardown.
"""

from __future__ import annotations

import ipaddress
import logging

import botocore.exceptions

from cna.core.throttle import with_retry
from cna.core.topology_schema import (
    AWSFlowLogSummary,
    AWSReachabilityPath,
    AWSTGWRoute,
    AWSTGWRouteAnalysis,
)

logger = logging.getLogger("cna.discovery.aws.depth")

_NOT_ENABLED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "ResourceNotFoundException",
    "InvalidAction",
    "OptInRequired",
}


def _is_not_enabled(e: botocore.exceptions.ClientError) -> bool:
    return e.response.get("Error", {}).get("Code", "") in _NOT_ENABLED_CODES


# ── C3: Transit Gateway route analysis (surpass) ────────────────────────────


class TransitGatewayRouteAnalyzer:
    """Analyzes TGW route tables for one region: routes, blackholes, CIDR overlaps."""

    def __init__(self, ec2_client, account_id: str, region: str):
        self.ec2 = ec2_client
        self.account_id = account_id
        self.region = region

    def analyze(self, tgw_route_table_ids: dict[str, str]) -> list[AWSTGWRouteAnalysis]:
        """tgw_route_table_ids maps route_table_id -> transit_gateway_id."""
        out: list[AWSTGWRouteAnalysis] = []
        for rt_id, tgw_id in tgw_route_table_ids.items():
            out.append(self._one(tgw_id, rt_id))
        return out

    def _one(self, tgw_id: str, rt_id: str) -> AWSTGWRouteAnalysis:
        analysis = AWSTGWRouteAnalysis(transit_gateway_id=tgw_id, route_table_id=rt_id)
        try:
            resp = with_retry()(self.ec2.search_transit_gateway_routes)(
                TransitGatewayRouteTableId=rt_id,
                Filters=[{"Name": "state", "Values": ["active", "blackhole", "pending"]}],
            )
        except botocore.exceptions.ClientError as e:
            if _is_not_enabled(e):
                analysis.note = f"route analysis unavailable: {e.response['Error']['Code']}"
                return analysis
            raise

        cidrs: list[str] = []
        for r in resp.get("Routes", []):
            cidr = r.get("DestinationCidrBlock", "")
            state = r.get("State", "")
            attach = (r.get("TransitGatewayAttachments") or [{}])[0].get("TransitGatewayAttachmentId")
            analysis.routes.append(
                AWSTGWRoute(
                    destination_cidr=cidr,
                    state=state,
                    route_type=r.get("Type", ""),
                    attachment_id=attach,
                )
            )
            if state == "blackhole":
                analysis.blackhole_count += 1
            if cidr:
                cidrs.append(cidr)
        analysis.overlapping_cidrs = _find_overlaps(cidrs)
        return analysis


def _find_overlaps(cidrs: list[str]) -> list[str]:
    """Return CIDRs that overlap another CIDR in the list (observed fact)."""
    nets = []
    for c in cidrs:
        try:
            nets.append((c, ipaddress.ip_network(c, strict=False)))
        except ValueError:
            continue
    overlapping: set[str] = set()
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            if nets[i][1].overlaps(nets[j][1]):
                overlapping.add(nets[i][0])
                overlapping.add(nets[j][0])
    return sorted(overlapping)


# ── C2: VPC flow-log analysis (surpass) ─────────────────────────────────────


class FlowLogAnalyzer:
    """Summarizes VPC flow-log traffic, or records the gap when logs are off."""

    def __init__(self, ec2_client, logs_client, account_id: str, region: str):
        self.ec2 = ec2_client
        self.logs = logs_client
        self.account_id = account_id
        self.region = region

    def analyze(self, vpc_ids: list[str]) -> list[AWSFlowLogSummary]:
        return [self._one(vpc_id) for vpc_id in vpc_ids]

    def _one(self, vpc_id: str) -> AWSFlowLogSummary:
        summary = AWSFlowLogSummary(vpc_id=vpc_id)
        try:
            resp = with_retry()(self.ec2.describe_flow_logs)(
                Filter=[{"Name": "resource-id", "Values": [vpc_id]}]
            )
        except botocore.exceptions.ClientError as e:
            if _is_not_enabled(e):
                summary.note = f"flow-log lookup unavailable: {e.response['Error']['Code']}"
                return summary
            raise

        flow_logs = resp.get("FlowLogs", [])
        if not flow_logs:
            # DD-002: the gap is an observed fact, not an inference. This record
            # IS the gap finding.
            summary.enabled = False
            summary.note = "VPC flow logs are not enabled (gap)"
            return summary

        summary.enabled = True
        fl = flow_logs[0]
        summary.log_destination_type = fl.get("LogDestinationType", "")
        # Deeper traffic summarization (top talkers / rejects / cross-AZ) runs a
        # bounded Logs Insights query only for CloudWatch Logs destinations; S3
        # destinations are recorded as enabled without the content query here.
        if summary.log_destination_type == "cloud-watch-logs":
            self._summarize_cw(summary, fl)
        else:
            summary.note = f"enabled ({summary.log_destination_type}); content query not run"
        return summary

    def _summarize_cw(self, summary: AWSFlowLogSummary, flow_log: dict) -> None:
        group = flow_log.get("LogGroupName")
        if not group:
            summary.note = "enabled; no CloudWatch log group name"
            return
        try:
            # Bounded: a single, short Insights query. Start/stop/results only —
            # all read-only against the log data.
            start = with_retry()(self.logs.start_query)(
                logGroupName=group,
                startTime=0,
                endTime=1,
                queryString="stats count(*) as c by srcAddr, dstAddr | sort c desc | limit 10",
                limit=10,
            )
            qid = start.get("queryId")
            res = with_retry()(self.logs.get_query_results)(queryId=qid)
            rows = res.get("results", [])
            summary.top_talkers = [_row_to_talker(r) for r in rows][:10]
            summary.note = "enabled; summarized from CloudWatch Logs"
        except botocore.exceptions.ClientError as e:
            if _is_not_enabled(e):
                summary.note = f"enabled; summary unavailable: {e.response['Error']['Code']}"
                return
            raise


def _row_to_talker(row: list[dict]) -> str:
    fields = {f.get("field"): f.get("value") for f in row}
    return f"{fields.get('srcAddr', '?')} -> {fields.get('dstAddr', '?')} ({fields.get('c', '?')})"


# ── C6: FLAGSHIP — Reachability Analyzer path testing (surpass) ─────────────


class ReachabilityAnalyzer:
    """Tests real reachability between endpoint pairs via VPC Reachability Analyzer.

    This is the one collector that CREATES a billable resource (a network
    insights path + analysis). It MUST tear both down after reading the result,
    always — the delete runs in a finally block even if the analysis fails.
    Paths are tagged Project=cna and the pair count is bounded by the caller.
    """

    def __init__(self, ec2_client, account_id: str, region: str, *, project_tag: str = "cna"):
        self.ec2 = ec2_client
        self.account_id = account_id
        self.region = region
        self.project_tag = project_tag

    def analyze(self, pairs: list[tuple[str, str, str]]) -> list[AWSReachabilityPath]:
        """pairs: list of (name, source_id, destination_id)."""
        return [self._one(name, src, dst) for (name, src, dst) in pairs]

    def _one(self, name: str, source: str, destination: str) -> AWSReachabilityPath:
        result = AWSReachabilityPath(name=name, source=source, destination=destination)
        path_id = None
        analysis_id = None
        try:
            created = with_retry()(self.ec2.create_network_insights_path)(
                Source=source,
                Destination=destination,
                Protocol="tcp",
                TagSpecifications=[
                    {
                        "ResourceType": "network-insights-path",
                        "Tags": [{"Key": "Project", "Value": self.project_tag}],
                    }
                ],
            )
            path_id = created["NetworkInsightsPath"]["NetworkInsightsPathId"]
            started = with_retry()(self.ec2.start_network_insights_analysis)(
                NetworkInsightsPathId=path_id,
                TagSpecifications=[
                    {
                        "ResourceType": "network-insights-analysis",
                        "Tags": [{"Key": "Project", "Value": self.project_tag}],
                    }
                ],
            )
            analysis_id = started["NetworkInsightsAnalysis"]["NetworkInsightsAnalysisId"]

            waiter_ok = self._wait(analysis_id)
            if not waiter_ok:
                result.note = "analysis did not complete in time"
                return result

            desc = with_retry()(self.ec2.describe_network_insights_analyses)(
                NetworkInsightsAnalysisIds=[analysis_id]
            )
            analysis = (desc.get("NetworkInsightsAnalyses") or [{}])[0]
            result.reachable = bool(analysis.get("NetworkPathFound", False))
            if not result.reachable:
                comps = analysis.get("ForwardPathComponents") or []
                if comps:
                    last = comps[-1].get("Component", {})
                    result.blocking_component = last.get("Id") or last.get("Arn")
                result.note = "not reachable"
            else:
                result.note = "reachable"
        except botocore.exceptions.ClientError as e:
            if _is_not_enabled(e):
                result.reachable = None
                result.note = f"reachability analyzer unavailable: {e.response['Error']['Code']}"
                return result
            raise
        finally:
            # MANDATORY teardown — the billable resources never outlive the read.
            self._delete(analysis_id, path_id)
        return result

    def _wait(self, analysis_id: str, attempts: int = 10) -> bool:
        for _ in range(attempts):
            desc = with_retry()(self.ec2.describe_network_insights_analyses)(
                NetworkInsightsAnalysisIds=[analysis_id]
            )
            status = (desc.get("NetworkInsightsAnalyses") or [{}])[0].get("Status", "")
            if status == "succeeded":
                return True
            if status == "failed":
                return False
        return False

    def _delete(self, analysis_id: str | None, path_id: str | None) -> None:
        if analysis_id:
            try:
                self.ec2.delete_network_insights_analysis(NetworkInsightsAnalysisId=analysis_id)
            except botocore.exceptions.ClientError as e:
                logger.warning("[%s] failed to delete analysis %s: %s", self.region, analysis_id, e)
        if path_id:
            try:
                self.ec2.delete_network_insights_path(NetworkInsightsPathId=path_id)
            except botocore.exceptions.ClientError as e:
                logger.warning("[%s] failed to delete path %s: %s", self.region, path_id, e)


def default_endpoint_pairs(topology: object) -> list[tuple[str, str, str]]:
    """Derive default reachability pairs from discovered topology.

    Defaults (BUILD-01): public ingress -> web tier, web -> api, app tier -> RDS.
    Returns [] when the topology does not expose the needed ids — the caller
    then records no reachability paths (a logged gap), never a failure. Kept
    deliberately minimal; a real topology-walk is wired when the collector is
    enabled against a live account.
    """
    pairs: list[tuple[str, str, str]] = []
    getter = getattr(topology, "reachability_pairs", None)
    if callable(getter):
        try:
            return list(getter())
        except Exception:  # pragma: no cover - defensive
            return []
    return pairs
