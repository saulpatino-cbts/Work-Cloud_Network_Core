"""Unit tests for the ``terraform-aws`` area findings (Requirement 4.1).

Covers the verify-then-close-gaps record for the AWS Terraform audit (spec task
7.1): the per-module verified-compliant records for all eight module boundaries,
the account-independent best-practice fixes applied in-tree (static-site
SSE+versioning, SNS encryption, ALB drop-invalid-headers), the residual fixable
gaps left for an operator choice, and the gated dependencies recorded for spec
task 7.2 to map to R-001..R-006. The gated→blocker mapping itself is NOT this
task's job, so no finding here carries a blocker_id.
"""

from cna.review import AREAS, Severity, consolidate
from cna.review.areas import AWS_MODULES, terraform_aws_findings


def test_findings_are_well_formed_and_in_area():
    findings = terraform_aws_findings()
    assert findings, "the area must record at least one finding"
    for finding in findings:
        assert finding.area == "terraform-aws"
        assert finding.area in AREAS
        assert finding.proposed_action.strip()


def test_covers_all_eight_module_boundaries():
    """4.1: every one of the eight AWS module boundaries is audited/recorded."""
    findings = terraform_aws_findings()
    audited = {
        f.subject.rsplit("/", 1)[-1]
        for f in findings
        if f.dedup_key.startswith("terraform-aws:module-audited:")
    }
    assert audited == set(AWS_MODULES)
    assert len(AWS_MODULES) == 8


def test_applied_fixes_are_recorded():
    """The three account-independent corrections applied in-tree are recorded."""
    findings = terraform_aws_findings()
    keys = {f.dedup_key for f in findings}
    assert "terraform-aws:s3-static-sse-versioning" in keys
    assert "terraform-aws:sns-topic-encryption" in keys
    assert "terraform-aws:alb-drop-invalid-headers" in keys


def test_gated_findings_name_every_dependency_kind():
    """Each R-001..R-006 dependency kind is recorded with a gated: marker."""
    findings = terraform_aws_findings()
    gated_kinds = {
        f.dedup_key.split("gated:", 1)[1] for f in findings if "terraform-aws:gated:" in f.dedup_key
    }
    assert gated_kinds == {
        "account",
        "state-backend",
        "oidc-role",
        "certificate",
        "bedrock",
        "runtime-secret",
    }


def test_task_7_1_records_no_blocker_ids():
    """7.2 owns the R-001..R-006 mapping, so 7.1 records no blocker_id."""
    findings = terraform_aws_findings()
    assert all(f.blocker_id is None for f in findings)


def test_findings_consolidate_into_fixable_entries():
    """Without blocker ids, findings consolidate into fixable plan entries.

    The gated→escalation reclassification is spec task 7.2's job; here the raw
    findings collapse into ordered, fixable entries that reference this area.
    """
    plan = consolidate(terraform_aws_findings())
    assert plan.entries
    for entry in plan.entries:
        assert entry.is_escalation is False
        assert entry.blocker_id is None
        assert "terraform-aws" in entry.referenced_areas
    # Severity ordering (Property 3) holds on the consolidated plan.
    severities = [entry.severity for entry in plan.entries]
    assert severities == sorted(severities, reverse=True)


def test_highest_severity_findings_are_the_gated_prerequisites():
    """Account / state-backend / OIDC-role gates are the top-severity items."""
    findings = terraform_aws_findings()
    high = {f.dedup_key for f in findings if f.severity is Severity.HIGH}
    assert "terraform-aws:gated:account" in high
    assert "terraform-aws:gated:state-backend" in high
    assert "terraform-aws:gated:oidc-role" in high
