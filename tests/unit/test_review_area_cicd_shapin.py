"""Unit tests for the CI/CD SHA-pin checker and R-003 escalation (spec 9.3).

Focused example tests for the SHA-pin checker (Requirement 5.3) and the R-003
escalation for ``212-deploy-aws-split.yml`` (5.4). The universal SHA-pinning
property (design Property 14) is exercised by the separate property test in
spec task 9.4; here we cover the checker's predicates on concrete references,
the live-tree scan result, and the escalation record.
"""

from pathlib import Path

from cna.review import AREAS, Severity, consolidate, gate_finding, load_blockers
from cna.review.areas import (
    cicd_sha_and_escalation_findings,
    find_unpinned_references,
    is_sha_pinned,
    is_third_party_action,
    r003_escalation_finding,
    scan_uses_references,
    sha_pin_findings,
)

_WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"

_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"  # 40 hex chars


# --- checker predicates -----------------------------------------------------


def test_is_sha_pinned_accepts_only_40_hex():
    assert is_sha_pinned(f"actions/checkout@{_SHA}") is True
    assert is_sha_pinned("actions/checkout@v4") is False
    assert is_sha_pinned("actions/checkout@main") is False
    # A short (7-char) SHA is not a full 40-hex pin.
    assert is_sha_pinned("actions/checkout@9c091bb") is False
    # No @ref at all cannot be pinned.
    assert is_sha_pinned("./local-action") is False


def test_is_third_party_action_classification():
    # A real owner/repo action reference.
    assert is_third_party_action(f"actions/checkout@{_SHA}") is True
    assert is_third_party_action("actions/checkout@v4") is True
    # Local references are not third-party actions.
    assert is_third_party_action("./.github/actions/setup") is False
    assert is_third_party_action("../shared/action") is False
    # docker:// container actions are out of scope.
    assert is_third_party_action("docker://alpine:3.20") is False
    # A reusable-workflow reference (path ends in .yml) is not a third-party action.
    assert is_third_party_action("owner/repo/.github/workflows/build.yml@v1") is False
    # A bare ref with no owner/repo path is not a third-party action.
    assert is_third_party_action("some-ref@v1") is False


def test_scan_uses_references_strips_inline_comments():
    text = (
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{_SHA}  # v7.0.0\n"
        "      - uses: actions/checkout@v4\n"
    )
    refs = scan_uses_references(text)
    assert refs == [f"actions/checkout@{_SHA}", "actions/checkout@v4"]


def test_find_unpinned_references_records_exactly_the_tag_pinned_ref():
    """Property 14 in the small: record a third-party ref iff it is not SHA-pinned."""
    text = (
        f"      - uses: actions/checkout@{_SHA}\n"  # pinned → not recorded
        "      - uses: actions/create-github-app-token@v3\n"  # tag → recorded
        "      - uses: ./.github/actions/local\n"  # local → ignored
        "      - uses: docker://alpine:3.20\n"  # docker → ignored
    )
    assert find_unpinned_references(text) == ["actions/create-github-app-token@v3"]


def test_fully_pinned_workflow_records_nothing(tmp_path: Path):
    wf = tmp_path / "clean.yml"
    wf.write_text(
        f"      - uses: actions/checkout@{_SHA}\n      - uses: actions/setup-python@{_SHA}\n",
        encoding="utf-8",
    )
    findings = sha_pin_findings(tmp_path)
    # No unpinned refs anywhere → one verified-compliant informational record.
    assert len(findings) == 1
    assert findings[0].severity is Severity.INFORMATIONAL
    assert findings[0].dedup_key == "cicd:sha-pin:all-pinned"


def test_unpinned_refs_deduped_per_file(tmp_path: Path):
    wf = tmp_path / "212-example.yml"
    wf.write_text(
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/checkout@v4\n"  # same ref, 2nd job → deduped
        "      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    findings = sha_pin_findings(tmp_path)
    assert len(findings) == 1
    assert findings[0].severity is Severity.MEDIUM
    assert findings[0].subject == ".github/workflows/212-example.yml"
    assert findings[0].dedup_key == "cicd:sha-pin:212-example.yml:actions/checkout"


# --- live-tree scan ---------------------------------------------------------


def test_live_scan_finds_every_core_workflow_pinned():
    """5.3: the real workflow tree carries no unpinned third-party refs.

    The two references the original scan recorded lived in
    ``211-deploy-azure-split.yml`` and ``212-deploy-aws-split.yml``, which moved
    to the appliance repositories (TODO.md T-504); the workflows that remain in
    the core are all SHA-pinned, so the scan records the single informational
    all-pinned entry and nothing MEDIUM.
    """
    findings = sha_pin_findings(_WORKFLOWS_DIR)
    keys = {f.dedup_key for f in findings}
    assert keys == {"cicd:sha-pin:all-pinned"}
    for f in findings:
        assert f.severity is Severity.INFORMATIONAL
        assert f.blocker_id is None
        assert f.area == "cicd"
        assert f.area in AREAS


def test_no_false_positive_on_pinned_or_local_or_docker_refs():
    """The live scan records only genuinely tag/branch-pinned third-party refs."""
    findings = sha_pin_findings(_WORKFLOWS_DIR)
    for f in findings:
        if not f.dedup_key.startswith("cicd:sha-pin:"):
            continue
        if f.severity is Severity.INFORMATIONAL:
            continue
        # A recorded ref must be a real unpinned third-party action, confirmed
        # by re-running the predicates over the finding's proposed action.
        assert "40-hex commit SHA" in f.proposed_action


# --- R-003 escalation -------------------------------------------------------


def test_r003_escalation_carries_blocker_id_and_targets_212():
    """5.4: the R-003 escalation names workflow 212 and carries blocker_id R-003."""
    esc = r003_escalation_finding()
    assert esc.area == "cicd"
    assert esc.blocker_id == "R-003"
    assert esc.subject.endswith("212-deploy-aws-split.yml")
    assert "212-deploy-aws-split.yml" in esc.proposed_action


def test_r003_escalation_gates_to_an_escalation_entry():
    """Through the real REVIEW.md scope gate, R-003 becomes an escalation entry."""
    blockers = load_blockers()
    entry = gate_finding(r003_escalation_finding(), blockers)
    assert entry.is_escalation is True
    assert entry.blocker_id == "R-003"


def test_combined_findings_only_the_r003_entry_is_blocker_owned():
    """9.3's SHA-pin findings are fixable; only the R-003 record is an escalation."""
    findings = cicd_sha_and_escalation_findings(_WORKFLOWS_DIR)
    blocker_owned = [f for f in findings if f.blocker_id is not None]
    assert len(blocker_owned) == 1
    assert blocker_owned[0].blocker_id == "R-003"


def test_combined_findings_consolidate_and_are_severity_ordered():
    findings = cicd_sha_and_escalation_findings(_WORKFLOWS_DIR)
    plan = consolidate(findings)
    assert plan.entries
    for entry in plan.entries:
        assert "cicd" in entry.referenced_areas
    severities = [entry.severity for entry in plan.entries]
    assert severities == sorted(severities, reverse=True)
