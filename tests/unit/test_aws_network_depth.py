"""Unit tests for BUILD-01 surpass collectors C2/C3/C4/C6.

Mocked boto3 only. Focus: observed-state honesty, graceful degradation, bounded
cost calls, and — for the flagship Reachability Analyzer — the MANDATORY
teardown of the billable path/analysis resources in every exit path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import botocore.exceptions
import pytest

from cna.modules.network.discovery.aws_cost import (
    DEFAULT_WINDOW_DAYS,
    AWSCostCollector,
)
from cna.modules.network.discovery.aws_network_depth import (
    FlowLogAnalyzer,
    ReachabilityAnalyzer,
    TransitGatewayRouteAnalyzer,
    _find_overlaps,
)


def _client_error(code: str, op: str = "Op"):
    return botocore.exceptions.ClientError({"Error": {"Code": code, "Message": code}}, op)


# ── C3: TGW route analysis ──────────────────────────────────────────────────


class TestTGWRouteAnalysis:
    def test_routes_blackholes_and_overlaps(self):
        ec2 = MagicMock()
        ec2.search_transit_gateway_routes.return_value = {
            "Routes": [
                {
                    "DestinationCidrBlock": "10.0.0.0/16",
                    "State": "active",
                    "Type": "static",
                    "TransitGatewayAttachments": [{"TransitGatewayAttachmentId": "tgw-attach-1"}],
                },
                {"DestinationCidrBlock": "10.0.1.0/24", "State": "active", "Type": "propagated"},
                {"DestinationCidrBlock": "192.168.0.0/16", "State": "blackhole"},
            ]
        }
        a = TransitGatewayRouteAnalyzer(ec2, "acct", "us-east-1").analyze({"tgw-rtb-1": "tgw-1"})[0]
        assert a.transit_gateway_id == "tgw-1"
        assert len(a.routes) == 3
        assert a.blackhole_count == 1
        # 10.0.0.0/16 and 10.0.1.0/24 overlap
        assert "10.0.0.0/16" in a.overlapping_cidrs
        assert "10.0.1.0/24" in a.overlapping_cidrs
        assert "192.168.0.0/16" not in a.overlapping_cidrs

    def test_degrades_on_denied(self):
        ec2 = MagicMock()
        ec2.search_transit_gateway_routes.side_effect = _client_error("AccessDenied")
        a = TransitGatewayRouteAnalyzer(ec2, "acct", "us-east-1").analyze({"tgw-rtb-1": "tgw-1"})[0]
        assert a.routes == []
        assert "AccessDenied" in a.note

    def test_overlap_helper_ignores_invalid(self):
        assert _find_overlaps(["not-a-cidr", "10.0.0.0/8", "10.1.0.0/16"]) == [
            "10.0.0.0/8",
            "10.1.0.0/16",
        ]


# ── C2: flow-log analysis ───────────────────────────────────────────────────


class TestFlowLogAnalysis:
    def test_gap_recorded_when_disabled(self):
        ec2 = MagicMock()
        ec2.describe_flow_logs.return_value = {"FlowLogs": []}
        s = FlowLogAnalyzer(ec2, MagicMock(), "acct", "us-east-1").analyze(["vpc-1"])[0]
        assert s.enabled is False
        assert "not enabled" in s.note

    def test_s3_destination_enabled_without_content_query(self):
        ec2 = MagicMock()
        ec2.describe_flow_logs.return_value = {"FlowLogs": [{"LogDestinationType": "s3"}]}
        logs = MagicMock()
        s = FlowLogAnalyzer(ec2, logs, "acct", "us-east-1").analyze(["vpc-1"])[0]
        assert s.enabled is True
        assert s.log_destination_type == "s3"
        logs.start_query.assert_not_called()

    def test_cloudwatch_destination_summarized(self):
        ec2 = MagicMock()
        ec2.describe_flow_logs.return_value = {
            "FlowLogs": [{"LogDestinationType": "cloud-watch-logs", "LogGroupName": "/vpc/fl"}]
        }
        logs = MagicMock()
        logs.start_query.return_value = {"queryId": "q1"}
        logs.get_query_results.return_value = {
            "results": [
                [
                    {"field": "srcAddr", "value": "10.0.0.1"},
                    {"field": "dstAddr", "value": "10.0.0.2"},
                    {"field": "c", "value": "99"},
                ]
            ]
        }
        s = FlowLogAnalyzer(ec2, logs, "acct", "us-east-1").analyze(["vpc-1"])[0]
        assert s.enabled is True
        assert s.top_talkers == ["10.0.0.1 -> 10.0.0.2 (99)"]


# ── C4: Cost Explorer (bounded) ─────────────────────────────────────────────


class TestCost:
    def test_default_three_windows(self):
        ce = MagicMock()
        ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
        records = AWSCostCollector(ce, "acct").collect()
        assert [r.window_days for r in records] == list(DEFAULT_WINDOW_DAYS)
        # bounded: exactly one call per window, never more
        assert ce.get_cost_and_usage.call_count == len(DEFAULT_WINDOW_DAYS)

    def test_only_network_usage_types_counted(self):
        ce = MagicMock()
        ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["USE1-NatGateway-Hours"],
                            "Metrics": {"UnblendedCost": {"Amount": "12.50", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["USE1-DataTransfer-Out-Bytes"],
                            "Metrics": {"UnblendedCost": {"Amount": "3.00", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["USE1-BoxUsage:t3.micro"],
                            "Metrics": {"UnblendedCost": {"Amount": "100.00", "Unit": "USD"}},
                        },
                    ]
                }
            ]
        }
        r = AWSCostCollector(ce, "acct", window_days=(30,)).collect()[0]
        assert r.total_cost == 15.5  # EC2 box usage excluded
        assert "USE1-NatGateway-Hours" in r.by_usage_type
        assert "USE1-BoxUsage:t3.micro" not in r.by_usage_type
        assert r.currency == "USD"

    def test_degrades_on_unavailable(self):
        ce = MagicMock()
        ce.get_cost_and_usage.side_effect = _client_error("DataUnavailableException")
        r = AWSCostCollector(ce, "acct", window_days=(30,)).collect()[0]
        assert r.total_cost == 0.0
        assert "unavailable" in r.note


# ── C6: FLAGSHIP Reachability Analyzer — teardown is mandatory ──────────────


def _reachable_ec2(status="succeeded", found=True):
    ec2 = MagicMock()
    ec2.create_network_insights_path.return_value = {
        "NetworkInsightsPath": {"NetworkInsightsPathId": "nip-1"}
    }
    ec2.start_network_insights_analysis.return_value = {
        "NetworkInsightsAnalysis": {"NetworkInsightsAnalysisId": "nia-1"}
    }
    ec2.describe_network_insights_analyses.return_value = {
        "NetworkInsightsAnalyses": [{"Status": status, "NetworkPathFound": found}]
    }
    return ec2


class TestReachabilityFlagship:
    def test_reachable_path(self):
        ec2 = _reachable_ec2(found=True)
        r = ReachabilityAnalyzer(ec2, "acct", "us-east-1").analyze(
            [("web->api", "eni-a", "eni-b")]
        )[0]
        assert r.reachable is True
        assert r.note == "reachable"

    def test_not_reachable_records_blocking_component(self):
        ec2 = _reachable_ec2(found=False)
        ec2.describe_network_insights_analyses.return_value = {
            "NetworkInsightsAnalyses": [
                {
                    "Status": "succeeded",
                    "NetworkPathFound": False,
                    "ForwardPathComponents": [{"Component": {"Id": "sg-block"}}],
                }
            ]
        }
        r = ReachabilityAnalyzer(ec2, "acct", "us-east-1").analyze(
            [("web->api", "eni-a", "eni-b")]
        )[0]
        assert r.reachable is False
        assert r.blocking_component == "sg-block"

    def test_teardown_always_runs_on_success(self):
        ec2 = _reachable_ec2()
        ReachabilityAnalyzer(ec2, "acct", "us-east-1").analyze([("p", "s", "d")])
        ec2.delete_network_insights_analysis.assert_called_once_with(
            NetworkInsightsAnalysisId="nia-1"
        )
        ec2.delete_network_insights_path.assert_called_once_with(NetworkInsightsPathId="nip-1")

    def test_teardown_runs_even_when_analysis_errors_midway(self):
        # start_analysis raises a non-not-enabled error AFTER the path was created:
        # the path must still be deleted (finally), and the error must propagate.
        ec2 = MagicMock()
        ec2.create_network_insights_path.return_value = {
            "NetworkInsightsPath": {"NetworkInsightsPathId": "nip-2"}
        }
        ec2.start_network_insights_analysis.side_effect = _client_error("InternalError")
        with pytest.raises(botocore.exceptions.ClientError):
            ReachabilityAnalyzer(ec2, "acct", "us-east-1").analyze([("p", "s", "d")])
        # path created -> must be torn down even though no analysis id exists
        ec2.delete_network_insights_path.assert_called_once_with(NetworkInsightsPathId="nip-2")
        ec2.delete_network_insights_analysis.assert_not_called()

    def test_unavailable_degrades_to_none(self):
        ec2 = MagicMock()
        ec2.create_network_insights_path.side_effect = _client_error("OptInRequired")
        r = ReachabilityAnalyzer(ec2, "acct", "us-east-1").analyze([("p", "s", "d")])[0]
        assert r.reachable is None
        assert "unavailable" in r.note
