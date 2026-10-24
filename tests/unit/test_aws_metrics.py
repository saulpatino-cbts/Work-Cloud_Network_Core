"""Unit tests for cna.modules.network.discovery.aws_metrics (BUILD-01 C1).

Mocked CloudWatch only — no AWS credentials, no network. Covers:
  - the mandatory default metric set applies when no override is given
  - a configurable override replaces the defaults
  - observed value aggregation from datapoints
  - "no datapoints" recorded as a fact (DD-002), not dropped
  - graceful degradation on access-denied / unavailable metrics (no raise)
  - a non-"not-enabled" ClientError still propagates (read-only correctness)
  - only mutation-free CloudWatch calls are used (read-only assertion)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import botocore.exceptions
import pytest

from cna.core.topology_schema import AWSNetworkMetric
from cna.modules.network.discovery.aws_metrics import (
    DEFAULT_METRICS,
    AWSMetricsCollector,
    MetricSpec,
    _Target,
)


def _client_error(code: str):
    return botocore.exceptions.ClientError(
        {"Error": {"Code": code, "Message": code}}, "GetMetricStatistics"
    )


@pytest.fixture
def nat_target():
    return _Target(resource_type="nat-gateway", resource_id="nat-abc", dimension_value="nat-abc")


class TestDefaults:
    def test_default_metric_set_applied_when_no_override(self, nat_target):
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {"Datapoints": [{"Sum": 1000.0, "Unit": "Bytes"}]}
        c = AWSMetricsCollector(cw, "123456789012", "us-east-1")
        results = c.collect([nat_target])
        # DEFAULT_METRICS has two nat-gateway specs -> two results for this target.
        nat_results = [r for r in results if r.resource_id == "nat-abc"]
        assert len(nat_results) == 2
        assert all(isinstance(r, AWSNetworkMetric) for r in nat_results)
        assert all(r.value == 1000.0 for r in nat_results)

    def test_default_metrics_constant_is_nonempty(self):
        assert len(DEFAULT_METRICS) >= 5


class TestOverride:
    def test_configurable_override_replaces_defaults(self, nat_target):
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {"Datapoints": [{"Average": 7.0, "Unit": "Count"}]}
        spec = MetricSpec(
            "nat-gateway", "AWS/NATGateway", "ActiveConnectionCount", "NatGatewayId", "Average"
        )
        c = AWSMetricsCollector(cw, "acct", "us-east-1", metric_specs=[spec])
        results = c.collect([nat_target])
        assert len(results) == 1
        assert results[0].metric_name == "ActiveConnectionCount"
        assert results[0].statistic == "Average"
        assert results[0].value == 7.0


class TestObservedStateHonesty:
    def test_no_datapoints_recorded_as_fact(self, nat_target):
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        c = AWSMetricsCollector(cw, "acct", "us-east-1", metric_specs=[DEFAULT_METRICS[0]])
        r = c.collect([nat_target])[0]
        assert r.value is None
        assert r.note == "no datapoints"

    def test_aggregates_multiple_datapoints(self, nat_target):
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Sum": 10.0, "Unit": "Bytes"}, {"Sum": 5.0, "Unit": "Bytes"}]
        }
        c = AWSMetricsCollector(cw, "acct", "us-east-1", metric_specs=[DEFAULT_METRICS[0]])
        r = c.collect([nat_target])[0]
        assert r.value == 15.0


class TestGracefulDegradation:
    @pytest.mark.parametrize(
        "code", ["AccessDenied", "AccessDeniedException", "ResourceNotFoundException"]
    )
    def test_not_enabled_codes_degrade_without_raising(self, nat_target, code):
        cw = MagicMock()
        cw.get_metric_statistics.side_effect = _client_error(code)
        c = AWSMetricsCollector(cw, "acct", "us-east-1", metric_specs=[DEFAULT_METRICS[0]])
        r = c.collect([nat_target])[0]
        assert r.value is None
        assert code in r.note

    def test_unexpected_error_propagates(self, nat_target):
        cw = MagicMock()
        cw.get_metric_statistics.side_effect = _client_error("ThrottlingUnexpectedFatal")
        c = AWSMetricsCollector(cw, "acct", "us-east-1", metric_specs=[DEFAULT_METRICS[0]])
        with pytest.raises(botocore.exceptions.ClientError):
            c.collect([nat_target])


class TestReadOnly:
    def test_only_read_only_cloudwatch_calls(self, nat_target):
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        c = AWSMetricsCollector(cw, "acct", "us-east-1", metric_specs=[DEFAULT_METRICS[0]])
        c.collect([nat_target])
        called = {name for name, _, _ in cw.mock_calls}
        # Every CloudWatch method touched must be a read (get_*/list_*/describe_*).
        assert called
        assert all(m.split(".")[0].startswith(("get_", "list_", "describe_")) for m in called), (
            f"non-read CloudWatch call: {called}"
        )


class TestNoTargets:
    def test_empty_targets_returns_empty(self):
        cw = MagicMock()
        c = AWSMetricsCollector(cw, "acct", "us-east-1")
        assert c.collect([]) == []
        cw.get_metric_statistics.assert_not_called()
