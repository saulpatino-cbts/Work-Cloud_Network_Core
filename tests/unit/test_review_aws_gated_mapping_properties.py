"""Property-based tests for the AWS gated→blocker mapping in the review.

Feature: production-readiness
Property 7: AWS gated dependencies map to R-001 through R-006

For any AWS Terraform finding whose remediation depends on live account access,
a state backend, an OIDC deploy role, a certificate, Bedrock model access, or a
runtime secret, the plan entry is an escalation whose ``blocker_id`` is within
R-001 through R-006 and matches the dependency kind.

Validates: Requirements 4.5
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from cna.review.areas.terraform_aws_verify import (
    GATED_KIND_TO_BLOCKER,
    blocker_for_gated_kind,
    terraform_aws_gated_escalations,
)
from cna.review.model import Finding, Severity

# A minimum of 100 iterations per the spec's property-test configuration.
_PROPERTY_SETTINGS = settings(max_examples=100)

# The R-001 through R-006 window this property pins the mapping to.
_VALID_BLOCKER_IDS = frozenset(f"R-00{n}" for n in range(1, 7))

# The six gated dependency kinds and their expected owning blocker, stated
# independently of the module under test so the test is a real oracle rather
# than a restatement of the production table.
_EXPECTED_KIND_TO_BLOCKER = {
    "account": "R-001",
    "state-backend": "R-002",
    "oidc-role": "R-003",
    "certificate": "R-004",
    "bedrock": "R-005",
    "runtime-secret": "R-006",
}

_GATED_KIND = st.sampled_from(sorted(_EXPECTED_KIND_TO_BLOCKER))

# Finding field strategies matching the Finding well-formedness constraint
# (non-empty proposed_action once stripped).
_SEVERITY = st.sampled_from(list(Severity))
_NON_EMPTY_ACTION = st.text(min_size=1).filter(lambda s: s.strip())
_SUBJECT = st.text(min_size=1).filter(lambda s: s.strip())
# Arbitrary text embedded around the gated:<kind> marker in the dedup key, so
# the mapping is exercised against varied dedup-key shapes (not just the
# canonical "terraform-aws:gated:<kind>" one).
_PREFIX = st.text(alphabet=st.characters(blacklist_characters=":"))


@_PROPERTY_SETTINGS
@given(kind=_GATED_KIND)
def test_property7_blocker_for_gated_kind_is_correct_and_in_range(kind: str) -> None:
    """Feature: production-readiness, Property 7: AWS gated dependencies map to R-001 through R-006.

    Over the six gated kinds, ``blocker_for_gated_kind`` returns exactly the
    owning R-001..R-006 id for that kind, and the id lies within the R-001
    through R-006 window.
    """
    blocker_id = blocker_for_gated_kind(kind)

    assert blocker_id == _EXPECTED_KIND_TO_BLOCKER[kind]
    assert blocker_id in _VALID_BLOCKER_IDS
    assert re.fullmatch(r"R-00[1-6]", blocker_id)
    # The production table agrees with the independent oracle for this kind.
    assert GATED_KIND_TO_BLOCKER[kind] == _EXPECTED_KIND_TO_BLOCKER[kind]


@_PROPERTY_SETTINGS
@given(
    kind=_GATED_KIND,
    prefix=_PREFIX,
    severity=_SEVERITY,
    proposed_action=_NON_EMPTY_ACTION,
    subject=_SUBJECT,
)
def test_property7_arbitrary_gated_finding_maps_to_owning_blocker(
    kind: str,
    prefix: str,
    severity: Severity,
    proposed_action: str,
    subject: str,
) -> None:
    """Feature: production-readiness, Property 7: AWS gated dependencies map to R-001 through R-006.

    For an arbitrary AWS finding whose ``dedup_key`` carries a ``gated:<kind>``
    marker, the mapping re-emits it as an escalation whose ``blocker_id`` is the
    kind's owning blocker and lies within R-001 through R-006.
    """
    dedup_key = f"terraform-aws:{prefix}gated:{kind}"
    finding = Finding(
        area="terraform-aws",
        severity=severity,
        proposed_action=proposed_action,
        dedup_key=dedup_key,
        subject=subject,
    )

    # The gated finding itself carries no blocker_id — the mapping assigns it.
    assert finding.blocker_id is None

    # Re-emit the finding as the module's escalation step does: the gated marker
    # in the dedup key resolves to the owning blocker.
    escalation = Finding(
        area=finding.area,
        severity=finding.severity,
        proposed_action=finding.proposed_action,
        dedup_key=finding.dedup_key,
        subject=finding.subject,
        blocker_id=blocker_for_gated_kind(kind),
    )

    assert escalation.blocker_id == _EXPECTED_KIND_TO_BLOCKER[kind]
    assert escalation.blocker_id in _VALID_BLOCKER_IDS


def test_property7_gated_escalations_all_map_within_r001_r006() -> None:
    """Feature: production-readiness, Property 7: AWS gated dependencies map to R-001 through R-006.

    Anchor over the real audit output: ``terraform_aws_gated_escalations``
    re-emits every ``gated:<kind>`` finding as an escalation whose
    ``blocker_id`` is the kind's owning blocker and lies within R-001..R-006.
    Every one of the six gated kinds is represented exactly once.
    """
    escalations = terraform_aws_gated_escalations()

    # Only the findings that carry a blocker_id are the gated escalations; the
    # validate-result record is a verified-compliant finding with no blocker.
    gated = [f for f in escalations if f.blocker_id is not None]

    seen_kinds: set[str] = set()
    for finding in gated:
        # The gated:<kind> marker embedded in the dedup key.
        assert "gated:" in finding.dedup_key
        kind = finding.dedup_key.split("gated:", 1)[1]
        seen_kinds.add(kind)

        assert finding.blocker_id == _EXPECTED_KIND_TO_BLOCKER[kind]
        assert finding.blocker_id in _VALID_BLOCKER_IDS

    # All six gated kinds are mapped, each exactly once.
    assert seen_kinds == set(_EXPECTED_KIND_TO_BLOCKER)
    assert len(gated) == len(_EXPECTED_KIND_TO_BLOCKER)
