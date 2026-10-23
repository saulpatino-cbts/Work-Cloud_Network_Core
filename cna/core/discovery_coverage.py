"""Discovery coverage report.

DD-005/DD-016: Every blocked account or region is logged and included
in all final reports as a data quality caveat.
"""

from pydantic import BaseModel


class DiscoveryCoverageReport(BaseModel):
    accounts_attempted: int = 0
    accounts_succeeded: int = 0
    accounts_blocked: int = 0
    regions_attempted: list = []
    regions_succeeded: list = []
    regions_blocked: list = []
    services_unavailable: list = []
    coverage_percentage: float = 0.0
    block_reasons: list = []  # SCP, permission denied, throttle, etc.
    # Sources (subscription/account ids) added to the topology via an offline
    # batch record (BUILD-03) rather than a live scan. Recorded as a data-quality
    # caveat so a report can say which sources were imported vs discovered live
    # (R3.3). The ids stay attributed to their true source.
    imported_offline: list = []

    def calculate_coverage(self) -> None:
        if self.accounts_attempted > 0:
            self.coverage_percentage = round(
                (self.accounts_succeeded / self.accounts_attempted) * 100, 1
            )

    def note_imported_offline(self, source_ids: list[str]) -> None:
        """Record source ids that joined the topology via an offline batch import.

        Keeps the caveat idempotent (a re-import of the same source does not
        duplicate the entry) and sorted for stable reporting.
        """
        merged = set(self.imported_offline) | {s for s in source_ids if s}
        self.imported_offline = sorted(merged)
