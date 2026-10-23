"""AWS network metrics collection — Phase C (BUILD-01 C1).

Collects CloudWatch metrics for discovered network resources in one account +
region — the AWS match for the Azure network collector's Phase 2 metrics scan
(cna.modules.network.discovery.azure_discovery._run_metrics_scan).

Design principles (mirrors aws_discovery / aws_security):
  - Observed state only (DD-002): a metric is reported as returned; "no data" is
    recorded as a fact, never inferred.
  - cna.core.throttle.with_retry for rate limiting, same convention as the rest
    of discovery.
  - Graceful degradation: a metric that is unavailable or denied degrades to a
    record with a note, never a raised exception.
  - Configurable metric set with a MANDATORY default (BUILD-01 decision): the
    caller may pass its own metric spec list; when it does not, DEFAULT_METRICS
    applies. Defaults are a module constant, never inline at the call site.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import botocore.exceptions

from cna.core.throttle import with_retry
from cna.core.topology_schema import AWSNetworkMetric

logger = logging.getLogger("cna.discovery.aws.metrics")

_NOT_ENABLED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "ResourceNotFoundException",
    "InvalidParameterValue",
}


@dataclass(frozen=True)
class MetricSpec:
    """One CloudWatch metric to collect for a resource type.

    dimension_name is the CloudWatch dimension whose value is the resource id
    (e.g. "NatGatewayId"); resource_type is the label recorded on the result.
    """

    resource_type: str
    namespace: str
    metric_name: str
    dimension_name: str
    statistic: str = "Sum"


# Mandatory recommended default metric set (BUILD-01 R1). An engagement may
# override the list, but this always applies when no override is supplied.
DEFAULT_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec("nat-gateway", "AWS/NATGateway", "BytesOutToDestination", "NatGatewayId", "Sum"),
    MetricSpec("nat-gateway", "AWS/NATGateway", "BytesInFromDestination", "NatGatewayId", "Sum"),
    MetricSpec("transit-gateway", "AWS/TransitGateway", "BytesIn", "TransitGateway", "Sum"),
    MetricSpec("transit-gateway", "AWS/TransitGateway", "BytesOut", "TransitGateway", "Sum"),
    MetricSpec("load-balancer", "AWS/ApplicationELB", "RequestCount", "LoadBalancer", "Sum"),
    MetricSpec("load-balancer", "AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", "Sum"),
    MetricSpec("vpn", "AWS/VPN", "TunnelState", "VpnId", "Minimum"),
)


@dataclass
class _Target:
    """A resource to pull a metric dimension value for."""

    resource_type: str
    resource_id: str
    dimension_value: str


class AWSMetricsCollector:
    """Collects CloudWatch metrics for a single account + region.

    `metric_specs` is the configurable set; None means DEFAULT_METRICS.
    `window_hours` bounds the look-back (default 24h).
    """

    def __init__(
        self,
        cloudwatch_client,
        account_id: str,
        region: str,
        *,
        metric_specs: list[MetricSpec] | None = None,
        window_hours: int = 24,
    ):
        self.cw = cloudwatch_client
        self.account_id = account_id
        self.region = region
        self.specs = list(metric_specs) if metric_specs is not None else list(DEFAULT_METRICS)
        self.window_hours = window_hours

    def collect(self, targets: list[_Target]) -> list[AWSNetworkMetric]:
        """Collect each spec for every target of the matching resource type.

        Never raises for an unavailable metric — it degrades to a record with a
        note so a partial metric set is still returned.
        """
        results: list[AWSNetworkMetric] = []
        by_type: dict[str, list[_Target]] = {}
        for t in targets:
            by_type.setdefault(t.resource_type, []).append(t)

        end = datetime.now(UTC)
        start = end - timedelta(hours=self.window_hours)
        period = max(60, self.window_hours * 3600)  # one aggregate datapoint over the window

        for spec in self.specs:
            for target in by_type.get(spec.resource_type, []):
                results.append(self._one(spec, target, start, end, period))
        return results

    def _one(self, spec: MetricSpec, target: _Target, start, end, period: int) -> AWSNetworkMetric:
        base = AWSNetworkMetric(
            resource_id=target.resource_id,
            resource_type=spec.resource_type,
            namespace=spec.namespace,
            metric_name=spec.metric_name,
            statistic=spec.statistic,
            window_hours=self.window_hours,
        )
        try:
            resp = with_retry()(self.cw.get_metric_statistics)(
                Namespace=spec.namespace,
                MetricName=spec.metric_name,
                Dimensions=[{"Name": spec.dimension_name, "Value": target.dimension_value}],
                StartTime=start,
                EndTime=end,
                Period=period,
                Statistics=[spec.statistic],
            )
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in _NOT_ENABLED_CODES:
                base.note = f"metric unavailable: {code}"
                logger.debug(
                    "[%s/%s] %s/%s unavailable for %s: %s",
                    self.account_id,
                    self.region,
                    spec.namespace,
                    spec.metric_name,
                    target.resource_id,
                    code,
                )
                return base
            raise

        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            base.note = "no datapoints"
            return base
        # One aggregate value for the window.
        key = spec.statistic
        base.value = sum(float(dp.get(key, 0.0)) for dp in datapoints)
        base.unit = datapoints[0].get("Unit", "")
        return base
