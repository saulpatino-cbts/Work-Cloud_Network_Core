"""Unit tests for the ``terraform-aws`` verify + escalation step (spec task 7.2).

Covers the ``terraform validate`` gate result (Requirements 4.2/4.3) and the
gated→blocker mapping (Requirement 4.5): each ``gated:<kind>`` marker recorded by
the 7.1 audit maps to its owning ``REVIEW.md`` blocker among R-001 through R-006,
and every mapped finding gates to an ``Escalation_Record`` (no live apply/plan —
Requirement 4.6).
"""

from cna.review import AREAS, Severity, consolidate
from cna.review.areas import (
    GATED_KIND_TO_BLOCKER,
    blocker_for_gated_kind,
    terraform_aws_gated_escalations,
)
from cna.review.blockers import gate_finding, load_blockers

# The expected gated-kind → blocker mapping, stated independently of the module
# under test so a regression in the mapping is caught here.
_EXPECTED_MAPPING = {
    "account": "R-001",
    "state-backend": "R-002",
    "oidc-role": "R-003",
    "certificate": "R-004",
    "bedrock": "R-005",
    "runtime-secret": "R-006",
}


def test_findings_are_well_formed_and_in_area():
    findings = terraform_aws_gated_escalations()
    assert findings, "the verify step must record at least one finding"
    for finding in findings:
        assert finding.area == "terraform-aws"
        assert finding.area in AREAS
        assert finding.proposed_action.strip()


def test_gated_kind_to_blocker_mapping_is_r001_through_r006():
    """4.5: each gated dependency kind maps to the correct R-001..R-006 blocker."""
    assert GATED_KIND_TO_BLOCKER == _EXPECTED_MAPPING
    for kind, blocker_id in _EXPECTED_MAPPING.items():
        assert blocker_for_gated_kind(kind) == blocker_id


def test_every_gated_kind_maps_to_the_correct_blocker_id():
    """Each escalation finding carries the blocker id owning its gated kind."""
    escalations = [f for f in terraform_aws_gated_escalations() if f.blocker_id]
    # One escalation per gated dependency kind, no duplicates.
    by_kind = {f.dedup_key.split("gated:", 1)[1]: f.blocker_id for f in escalations}
    assert by_kind == _EXPECTED_MAPPING


def test_records_terraform_validate_result():
    """4.2/4.3: the terraform validate gate result is recorded for the AWS roots."""
    findings = terraform_aws_gated_escalations()

    result = next(
        f for f in findings if f.dedup_key == "terraform-aws:validate-result"
    )
    assert result.severity is Severity.INFORMATIONAL
    assert result.blocker_id is None
    action = result.proposed_action.lower()
    assert "validate" in action
    assert "-backend=false" in action


def test_gated_findings_gate_to_escalation_records():
    """4.5/4.6/10.4: every R-001..R-006 finding becomes an Escalation_Record."""
    blockers = load_blockers()
    escalations = [f for f in terraform_aws_gated_escalations() if f.blocker_id]
    assert len(escalations) == len(_EXPECTED_MAPPING)

    for finding in escalations:
        assert finding.blocker_id in blockers, finding.blocker_id
        entry = gate_finding(finding, blockers)
        assert entry.is_escalation is True
        assert entry.blocker_id == finding.blocker_id
        assert "terraform-aws" in entry.referenced_areas


def test_consolidation_yields_the_six_blocker_escalations():
    """Consolidation produces exactly the R-001..R-006 escalation entries."""
    plan = consolidate(terraform_aws_gated_escalations())

    assert plan.entries
    escalations = [e for e in plan.entries if e.is_escalation]
    blocker_ids = {e.blocker_id for e in escalations}
    assert blocker_ids == set(_EXPECTED_MAPPING.values())
    # The validate-result finding stays fixable (verified-compliant), not gated.
    fixable = [e for e in plan.entries if not e.is_escalation]
    assert any(e.dedup_key == "terraform-aws:validate-result" for e in fixable)
    for entry in fixable:
        assert entry.blocker_id is None


def test_no_live_apply_or_plan_action_is_emitted():
    """4.6: any mention of apply/plan is an explicit exclusion, never an action.

    The findings are records (escalations / verified-compliant), not executable
    actions; where a proposed action references ``apply`` or ``plan`` it does so
    to state that it was *not* run (e.g. "do not attempt a live apply", "no
    live 'terraform apply'").
    """
    for finding in terraform_aws_gated_escalations():
        action = finding.proposed_action.lower()
        if "apply" in action or "plan" in action:
            assert (
                "no live" in action
                or "do not attempt" in action
                or "cannot run" in action
            ), finding.dedup_key
