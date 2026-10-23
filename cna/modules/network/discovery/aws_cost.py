"""AWS network cost collection — Phase C (BUILD-01 C4, surpass).

Queries Cost Explorer for network-attributable spend for one account, over the
30/60/90-day windows that support recent-drift and quick-win analysis — a cost
dimension the Azure network collector has no equivalent of.

Design principles:
  - Observed state only (DD-002): figures are reported as returned and are
    static estimates — render with [VERIFY] (see AWSNetworkCost).
  - cna.core.throttle.with_retry for rate limiting.
  - BOUNDED: one Cost Explorer call per window (three total per account), each
    with an explicit, declared time range and MONTHLY granularity so the
    scan cost is known and small. No unbounded scans.
  - Graceful degradation: Cost Explorer not enabled / denied -> a record with a
    note, never a raised exception.
  - Account-level, not per region (Cost Explorer is a global, account-scoped
    service).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, timedelta

import botocore.exceptions

from cna.core.throttle import with_retry
from cna.core.topology_schema import AWSNetworkCost

logger = logging.getLogger("cna.discovery.aws.cost")

# Default windows (BUILD-01 decision): 30 = recent drift / what changed,
# 60/90 = trend and quick-win sizing.
DEFAULT_WINDOW_DAYS: tuple[int, ...] = (30, 60, 90)

# Usage-type substrings that are network-attributable. Cost Explorer USAGE_TYPE
# values embed these (e.g. "USE1-NatGateway-Hours", "DataTransfer-Out-Bytes").
_NETWORK_USAGE_SUBSTRINGS = (
    "NatGateway",
    "DataTransfer",
    "VpcEndpoint",
    "TransitGateway",
    "VPN",
    "PublicIPv4",
)

_NOT_ENABLED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "DataUnavailableException",
    "UnresolvableUsageUnitException",
}


def _is_network_usage(usage_type: str) -> bool:
    return any(s in usage_type for s in _NETWORK_USAGE_SUBSTRINGS)


class AWSCostCollector:
    """Collects network-attributable Cost Explorer spend for a single account."""

    def __init__(self, ce_client, account_id: str, *, window_days: tuple[int, ...] | None = None):
        self.ce = ce_client
        self.account_id = account_id
        self.windows = tuple(window_days) if window_days is not None else DEFAULT_WINDOW_DAYS

    def collect(self) -> list[AWSNetworkCost]:
        """One bounded Cost Explorer call per window. Returns one record each."""
        today = datetime_utc_date()
        return [self._one_window(days, today) for days in self.windows]

    def _one_window(self, days: int, today: date) -> AWSNetworkCost:
        record = AWSNetworkCost(account_id=self.account_id, window_days=days)
        start = (today - timedelta(days=days)).isoformat()
        end = today.isoformat()
        try:
            resp = with_retry()(self.ce.get_cost_and_usage)(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
            )
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in _NOT_ENABLED_CODES:
                record.note = f"cost explorer unavailable: {code}"
                logger.debug("[%s] Cost Explorer unavailable (%s)", self.account_id, code)
                return record
            raise

        total = 0.0
        by_type: dict[str, float] = {}
        for period in resp.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                usage_type = (group.get("Keys") or [""])[0]
                if not _is_network_usage(usage_type):
                    continue
                amount = float(
                    group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0.0)
                )
                by_type[usage_type] = round(by_type.get(usage_type, 0.0) + amount, 4)
                total += amount
                unit = group.get("Metrics", {}).get("UnblendedCost", {}).get("Unit")
                if unit:
                    record.currency = unit
        record.total_cost = round(total, 4)
        record.by_usage_type = by_type
        if not by_type:
            record.note = "no network-attributable spend in window"
        return record


def datetime_utc_date() -> date:
    """Today's date in UTC (isolated for test monkeypatching)."""
    from datetime import datetime

    return datetime.now(UTC).date()
