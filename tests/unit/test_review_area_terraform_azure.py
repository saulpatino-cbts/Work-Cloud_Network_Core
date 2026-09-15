"""Unit tests for the ``terraform-azure`` area findings (Requirement 3).

Assert the verify-then-close-gaps record for the Azure Terraform audit: the
storage-account network-exposure gap this task closes (3.1), the live-but-stale
dev-environment drift record (3.3), and the verified-compliant best-practice
baseline. The findings must be well-formed, drawn from the ``terraform-azure``
owner area, and — critically — stay *fixable* rather than escalations: R-007
(Azure provider registration) is resolved-but-not-closed so its subject is out
of scope and simply not touched here, and R-008 (live acceptance sign-off) is
recorded as an escalation by spec task 6.2, not this one.
"""

from cna.review import AREAS, Severity, consolidate
from cna.review.areas import (
    terraform_azure_findings,
    terraform_azure_verify_findings,
)
from cna.review.blockers import gate_finding, load_blockers


def test_findings_are_well_formed_and_in_area():
    findings = terraform_azure_findings()
    assert findings, "the area must record at least one finding"
    for finding in findings:
        assert finding.area == "terraform-azure"
        assert finding.area in AREAS
        assert finding.proposed_action.strip()


def test_records_storage_network_rules_gap():
    """3.1: the application storage account network-exposure gap is recorded."""
    findings = terraform_azure_findings()
    storage = next(
        f
        for f in findings
        if f.dedup_key
        == "terraform-azure:storage-account-network-rules-deny-default"
    )
    assert storage.severity is Severity.MEDIUM
    assert "Deny" in storage.proposed_action
    assert "storage" in storage.subject


def test_records_dev_environment_drift():
    """3.3: drift of the live-but-stale dev environment is recorded."""
    findings = terraform_azure_findings()
    drift = next(
        f
        for f in findings
        if f.dedup_key == "terraform-azure:dev-environment-live-drift"
    )
    assert "drift" in drift.proposed_action.lower()
    assert "dev" in drift.subject


def test_findings_are_fixable_not_escalations():
    """Requirement 3 area findings are engineering-fixable — no blocker id.

    R-007's subject (provider registration) is simply not among these findings,
    and R-008 (live sign-off) is owned by task 6.2 — so nothing here carries a
    blocker id.
    """
    for finding in terraform_azure_findings():
        assert finding.blocker_id is None


def test_findings_gate_to_fixable_entries():
    """The scope gate keeps every area finding fixable against real REVIEW.md."""
    blockers = load_blockers()
    for finding in terraform_azure_findings():
        entry = gate_finding(finding, blockers)
        assert entry.is_escalation is False
        assert entry.blocker_id is None


def test_findings_consolidate_into_fixable_entries():
    plan = consolidate(terraform_azure_findings())
    assert plan.entries
    for entry in plan.entries:
        assert entry.is_escalation is False
        assert entry.blocker_id is None
        assert "terraform-azure" in entry.referenced_areas


# --- spec task 6.2: terraform validate sweep + R-008 escalation ---------------


def test_verify_findings_are_well_formed_and_in_area():
    findings = terraform_azure_verify_findings()
    assert findings, "the verify step must record at least one finding"
    for finding in findings:
        assert finding.area == "terraform-azure"
        assert finding.area in AREAS
        assert finding.proposed_action.strip()


def test_records_terraform_validate_sweep():
    """3.2: the terraform validate result is recorded for the Azure roots."""
    findings = terraform_azure_verify_findings()
    sweep = next(
        f
        for f in findings
        if f.dedup_key == "terraform-azure:terraform-validate-sweep"
    )
    action = sweep.proposed_action.lower()
    assert "terraform validate" in action
    assert "-backend=false" in action
    # The validate sweep is a fixable/informational record, not an escalation.
    assert sweep.blocker_id is None


def test_r008_escalation_carries_blocker_id():
    """3.4: the live-acceptance finding carries blocker_id R-008."""
    findings = terraform_azure_verify_findings()
    r008 = next(f for f in findings if f.blocker_id == "R-008")
    assert r008.area == "terraform-azure"
    assert "sign-off" in r008.proposed_action.lower()


def test_r008_gates_to_an_escalation_record():
    """3.4/10.4: R-008 is Open, so its finding becomes an Escalation_Record."""
    blockers = load_blockers()
    assert "R-008" in blockers, "R-008 must be a real REVIEW.md blocker"

    r008 = next(
        f for f in terraform_azure_verify_findings() if f.blocker_id == "R-008"
    )
    entry = gate_finding(r008, blockers)
    assert entry.is_escalation is True
    assert entry.blocker_id == "R-008"


def test_verify_sweep_gates_to_a_fixable_entry():
    """The validate-sweep record stays fixable — no blocker id."""
    blockers = load_blockers()
    sweep = next(
        f
        for f in terraform_azure_verify_findings()
        if f.dedup_key == "terraform-azure:terraform-validate-sweep"
    )
    entry = gate_finding(sweep, blockers)
    assert entry.is_escalation is False
    assert entry.blocker_id is None


def test_verify_findings_consolidate_with_r008_escalation():
    """Consolidation yields exactly one R-008 escalation among the entries."""
    plan = consolidate(terraform_azure_verify_findings())
    assert plan.entries
    escalations = [e for e in plan.entries if e.is_escalation]
    assert len(escalations) == 1
    assert escalations[0].blocker_id == "R-008"
    assert "terraform-azure" in escalations[0].referenced_areas
