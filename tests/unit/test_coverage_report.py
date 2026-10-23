"""Unit tests for discovery coverage report (DD-005/DD-016)."""

from cna.core.discovery_coverage import DiscoveryCoverageReport


def test_coverage_partial():
    r = DiscoveryCoverageReport(accounts_attempted=10, accounts_succeeded=8)
    r.calculate_coverage()
    assert r.coverage_percentage == 80.0


def test_coverage_full():
    r = DiscoveryCoverageReport(accounts_attempted=5, accounts_succeeded=5)
    r.calculate_coverage()
    assert r.coverage_percentage == 100.0


def test_coverage_zero_attempted():
    r = DiscoveryCoverageReport(accounts_attempted=0, accounts_succeeded=0)
    r.calculate_coverage()
    assert r.coverage_percentage == 0.0


# ── BUILD-03: imported-offline caveat (R3.3) ───────────────────────────────


def test_note_imported_offline_records_sources():
    r = DiscoveryCoverageReport()
    r.note_imported_offline(["111111111111", "sub-1"])
    assert r.imported_offline == ["111111111111", "sub-1"]


def test_note_imported_offline_is_idempotent_and_sorted():
    r = DiscoveryCoverageReport()
    r.note_imported_offline(["sub-2", "sub-1"])
    r.note_imported_offline(["sub-1", "sub-3"])  # sub-1 repeated
    assert r.imported_offline == ["sub-1", "sub-2", "sub-3"]


def test_note_imported_offline_ignores_empty():
    r = DiscoveryCoverageReport()
    r.note_imported_offline(["", "sub-1", ""])
    assert r.imported_offline == ["sub-1"]


def test_import_result_offline_source_ids_merges_imported_and_replaced():
    from cna.core.batch_record import ImportResult

    res = ImportResult(imported=["a", "b"], replaced=["c"], skipped=["d"])
    assert res.offline_source_ids() == ["a", "b", "c"]  # skipped excluded, sorted
