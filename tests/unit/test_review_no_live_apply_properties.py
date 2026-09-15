"""Property-based tests: no live AWS apply is emitted by the review.

Feature: production-readiness
Property 9: No live AWS apply is emitted

*For any* AWS remediation action set produced by the review, no action has a
live-apply (or live account ``plan``) action type. The AWS area emits
:class:`~cna.review.model.Finding` *records* — escalations and
verified-compliant outcomes — never executable actions. A finding therefore
never carries an ``apply``/``plan`` action verb; where its ``proposed_action``
text mentions apply/plan it does so only in a negating / exclusion context
("no live apply", "do not attempt", "cannot run", "escalate", "not run",
"skipped").

The invariant is exercised over arbitrary subsets and orderings of the two
AWS producers (:func:`terraform_aws_findings` and
:func:`terraform_aws_gated_escalations`), so it holds for *any* AWS action set
the review might assemble, not just the full one.

Validates: Requirements 4.6
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from cna.review.areas import (
    terraform_aws_findings,
    terraform_aws_gated_escalations,
)
from cna.review.model import Finding

# A minimum of 100 iterations per the spec's property-test configuration.
_PROPERTY_SETTINGS = settings(max_examples=100)

# The complete AWS action set the review can produce: the 7.1 audit findings and
# the 7.2 verify + gated escalations. Every AWS "action" the plan ever assembles
# is drawn from this pool, so the invariant over arbitrary subsets/orderings of
# it covers any set the review might emit.
_AWS_FINDINGS: tuple[Finding, ...] = tuple(
    terraform_aws_findings() + terraform_aws_gated_escalations()
)

# Phrases that turn a live apply/plan mention into an explicit exclusion rather
# than an emitted action. If a proposed_action references a live terraform
# apply/plan it MUST also carry one of these, proving it documents that the
# action was NOT taken.
_EXCLUSION_MARKERS: tuple[str, ...] = (
    "no live",
    "do not attempt",
    "cannot run",
    "escalate",
    "not run",
    "never applied",
    "skipped",
    "-backend=false",
)

# The *live-action* surface Property 9 forbids: a live ``terraform apply`` or an
# account ``terraform plan`` / ``plan against a real account``. Matching this
# phrasing (rather than the bare word "applied") avoids false positives on
# in-tree config edits, which Requirement 4.6 explicitly permits — the audit
# fixes .tf files ("Applied by this task") without running any live command.
_LIVE_APPLY_OR_PLAN = re.compile(
    r"terraform\s+(apply|plan)"  # `terraform apply` / `terraform plan`
    r"|live\s+(apply|'?terraform apply'?)"  # "live apply", "live 'terraform apply'"
    r"|(account|real account)\s+.*\bplan\b"  # account `plan`
    r"|\bplan\b.*(against a real account|real account)",
    re.IGNORECASE,
)


def _is_record_not_action(finding: Finding) -> bool:
    """A finding is a record, never an executable apply/plan action.

    A ``Finding`` has no action-type field at all — it carries an ``area``, a
    ``severity``, a ``proposed_action`` description, a ``dedup_key``, a
    ``subject`` and an optional ``blocker_id``. There is no attribute by which a
    finding could declare a live ``apply`` or account ``plan`` action type, so a
    finding structurally cannot *be* an executable action.
    """
    action_type_attrs = ("action_type", "action", "command", "live", "apply", "plan")
    return not any(hasattr(finding, attr) for attr in action_type_attrs)


def _apply_plan_mention_is_excluded(text: str) -> bool:
    """Any live apply/plan mention appears only in a negating/exclusion context.

    In-tree config edits (e.g. "Applied by this task") are permitted by
    Requirement 4.6 and do not count as a live action; only a ``terraform
    apply``/account ``plan`` phrasing is guarded, and it must be negated.
    """
    lowered = text.lower()
    if not _LIVE_APPLY_OR_PLAN.search(lowered):
        return True
    return any(marker in lowered for marker in _EXCLUSION_MARKERS)


# A strategy over arbitrary subsets of the AWS findings, in arbitrary order:
# permute the pool, then take an arbitrary-length prefix. This yields every
# ordering and every subset the review could assemble into an action set.
_AWS_ACTION_SET = st.permutations(_AWS_FINDINGS).flatmap(
    lambda ordered: st.integers(min_value=0, max_value=len(ordered)).map(
        lambda n: list(ordered[:n])
    )
)


def test_pool_is_non_empty() -> None:
    """Guard: the AWS producers actually emit findings to reason over."""
    assert _AWS_FINDINGS, "expected the AWS area to produce at least one finding"


@_PROPERTY_SETTINGS
@given(action_set=_AWS_ACTION_SET)
def test_property9_no_live_apply_emitted(action_set: list[Finding]) -> None:
    """Feature: production-readiness, Property 9: No live AWS apply is emitted.

    For any AWS action set (any subset, any ordering) produced by the review,
    every entry is a record (no executable apply/plan action type), and where an
    entry's ``proposed_action`` mentions apply/plan it does so only to state the
    action was not taken.
    """
    for finding in action_set:
        # 1. It is a record, not an executable action: no live-apply/plan type.
        assert _is_record_not_action(finding), finding.dedup_key
        # 2. Any live apply/plan mention is a negation/exclusion, never an action.
        assert _apply_plan_mention_is_excluded(finding.proposed_action), finding.dedup_key


@_PROPERTY_SETTINGS
@given(action_set=_AWS_ACTION_SET)
def test_property9_no_finding_declares_a_live_action_field(
    action_set: list[Finding],
) -> None:
    """Feature: production-readiness, Property 9: No live AWS apply is emitted.

    Reinforces the structural half of the invariant across arbitrary action
    sets: no finding exposes an action-type / command / apply / plan attribute
    through which a live apply could be requested.
    """
    for finding in action_set:
        assert not hasattr(finding, "action_type"), finding.dedup_key
        assert not hasattr(finding, "command"), finding.dedup_key
        # The only apply/plan-shaped surface is free text, guarded above.
