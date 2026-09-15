"""Verification + gated→blocker escalation for the ``terraform-aws`` area.

Spec task 7.2. This module owns two things the audit in
:mod:`cna.review.areas.terraform_aws` deliberately left open:

  1. **The ``terraform validate`` gate (Requirements 4.2, 4.3).** The AWS review
     process only runs once an evaluation of the AWS Terraform has occurred, and
     ``terraform validate`` is that gate. The commands run against every AWS root
     under ``infra/terraform/environments/aws/`` were, in order per root:

       * ``terraform fmt -check`` (whole AWS tree) — clean;
       * ``terraform init -backend=false`` — backend init skipped because the S3
         state backend is gated on R-002; and
       * ``terraform validate``.

     Two account-independent validate errors were surfaced and fixed in-tree by
     this task (they need no live account):

       * ``providers/aws/runtime/variables.tf`` — the ``name_prefix`` variable
         ``description`` contained an unescaped ``${name_prefix}`` that Terraform
         parsed as a template interpolation ("Variables may not be used here");
         escaped to ``$${name_prefix}``.
       * ``providers/aws/ai/main.tf`` — ``aws_bedrock_inference_profile.chat``
         set ``type = "APPLICATION"``, which the AWS provider marks read-only
         ("Invalid Configuration for Read-Only Attribute"); the line was removed
         (the provider computes the type from ``model_source``).

     After those fixes all four roots (``dev``/``prod`` × ``platform``/
     ``workload``) pass ``fmt -check`` + ``init -backend=false`` + ``validate``.
     The validate result is recorded here as a verified-compliant finding.

  2. **The gated→blocker mapping (Requirements 4.5, 4.6).** The audit recorded
     each human-gated dependency as a plain finding whose ``dedup_key`` carries a
     ``gated:<kind>`` marker but **no** ``blocker_id`` (so 7.1 and 7.2 do not
     double-count). This task maps each ``gated:<kind>`` marker to its owning
     ``REVIEW.md`` blocker among R-001 through R-006 and re-emits the finding as
     an *escalation-only* record (``blocker_id`` set), which the scope gate and
     consolidation then classify as an ``Escalation_Record``:

       * ``gated:account``        → R-001 (AWS account / admin access)
       * ``gated:state-backend``  → R-002 (S3 state backend + DynamoDB lock)
       * ``gated:oidc-role``      → R-003 (GitHub OIDC deploy role)
       * ``gated:certificate``    → R-004 (ACM certs + custom-domain decision)
       * ``gated:bedrock``        → R-005 (Bedrock model access opt-in)
       * ``gated:runtime-secret`` → R-006 (runtime secrets supplied at deploy)

     No live ``terraform apply`` and no account ``plan`` is ever emitted
     (Requirement 4.6); the gated findings are recorded as escalations, not
     attempted actions.
"""

from __future__ import annotations

from cna.review.areas.terraform_aws import terraform_aws_findings
from cna.review.model import Finding, Severity

_AREA = "terraform-aws"

# The four authored-but-never-applied AWS roots that were evaluated. Recorded so
# the verified-compliant validate finding names exactly what was checked.
AWS_ROOTS: tuple[str, ...] = (
    "infra/terraform/environments/aws/dev/platform",
    "infra/terraform/environments/aws/dev/workload",
    "infra/terraform/environments/aws/prod/platform",
    "infra/terraform/environments/aws/prod/workload",
)

# The ``gated:<kind>`` marker → owning ``REVIEW.md`` blocker mapping (R-001..R-006).
# Requirement 4.5: each AWS finding whose remediation depends on live account
# access / a state backend / an OIDC deploy role / a certificate / Bedrock access
# / a runtime secret maps to the corresponding blocker among R-001 through R-006.
GATED_KIND_TO_BLOCKER: dict[str, str] = {
    "account": "R-001",
    "state-backend": "R-002",
    "oidc-role": "R-003",
    "certificate": "R-004",
    "bedrock": "R-005",
    "runtime-secret": "R-006",
}


def _gated_kind(dedup_key: str) -> str | None:
    """Return the ``gated:<kind>`` marker embedded in a dedup key, if any.

    The audit encodes gated dependencies as ``terraform-aws:gated:<kind>``. A
    dedup key without that marker (a verified-compliant record, an applied fix,
    or a residual fixable gap) is not gated and yields ``None``.
    """
    marker = "gated:"
    if marker not in dedup_key:
        return None
    return dedup_key.split(marker, 1)[1]


def blocker_for_gated_kind(kind: str) -> str:
    """Map a ``gated:<kind>`` marker to its owning ``REVIEW.md`` blocker id.

    :param kind: the dependency kind (``account``, ``state-backend``,
        ``oidc-role``, ``certificate``, ``bedrock``, ``runtime-secret``).
    :returns: the owning blocker id within R-001 through R-006.
    :raises KeyError: if ``kind`` is not one of the six gated dependency kinds.
    """
    return GATED_KIND_TO_BLOCKER[kind]


def _validate_result_finding() -> Finding:
    """Record the ``terraform validate`` gate result (Requirements 4.2, 4.3).

    All four AWS roots pass ``fmt -check`` + ``init -backend=false`` +
    ``validate`` after this task's two account-independent fixes, so the gate is
    satisfied and the rest of the AWS review is authorized. Recorded
    ``INFORMATIONAL`` (a verified-compliant outcome, not a residual gap).
    """
    roots = ", ".join(AWS_ROOTS)
    return Finding(
        area=_AREA,
        severity=Severity.INFORMATIONAL,
        proposed_action=(
            "Verified compliant (Requirements 4.2/4.3): ran 'terraform fmt "
            "-check' (clean), 'terraform init -backend=false' (backend init "
            "skipped — S3 state backend is gated on R-002), and 'terraform "
            "validate' on every AWS root — "
            f"{roots}. Two account-independent validate errors were fixed in-tree "
            "by this task: the runtime name_prefix variable description had an "
            "unescaped ${name_prefix} interpolation (escaped to $${name_prefix}), "
            "and aws_bedrock_inference_profile.chat set the read-only 'type' "
            "attribute (removed). After the fixes all four roots validate "
            "successfully. No live 'terraform apply' or account 'plan' was run "
            "(Requirement 4.6)."
        ),
        dedup_key="terraform-aws:validate-result",
        subject="infra/terraform/environments/aws",
    )


def terraform_aws_gated_escalations() -> list[Finding]:
    """Return the R-001..R-006 escalation findings plus the validate result.

    Reads the audit's findings (:func:`terraform_aws_findings`), and for each one
    whose ``dedup_key`` carries a ``gated:<kind>`` marker re-emits it as an
    escalation-only :class:`~cna.review.model.Finding` carrying the owning
    ``blocker_id`` (R-001..R-006 per :data:`GATED_KIND_TO_BLOCKER`). The
    non-gated findings are left to the area's own emitter — this function adds
    only the escalation mapping (Requirement 4.5) and the ``terraform validate``
    gate result (Requirements 4.2/4.3). No live apply/plan action is produced
    (Requirement 4.6).

    :returns: the ``terraform validate`` verified-compliant finding followed by
        one escalation finding per gated dependency, each with its owning
        ``blocker_id`` set.
    :raises KeyError: if the audit records a ``gated:<kind>`` marker with no
        blocker mapping — every gated kind must map to R-001..R-006.
    """
    escalations: list[Finding] = []
    for finding in terraform_aws_findings():
        kind = _gated_kind(finding.dedup_key)
        if kind is None:
            continue
        blocker_id = blocker_for_gated_kind(kind)
        escalations.append(
            Finding(
                area=finding.area,
                severity=finding.severity,
                proposed_action=finding.proposed_action,
                dedup_key=finding.dedup_key,
                subject=finding.subject,
                blocker_id=blocker_id,
            )
        )

    return [_validate_result_finding()] + escalations
