"""Findings for the ``python-engine-api`` area (Requirement 2 correctness).

This is a *verify-then-close-gaps* record for the ``cna/`` core, the
``apps/cna-api`` FastAPI service, and the (now retired) ``apps/cna-worker``
decision. The
audit against Requirement 2 confirmed:

  * **2.1 — `/intake` honesty (verified compliant).** ``apps/cna-api/main.py``
    returns an honest ``501`` (``Outcome.NOT_IMPLEMENTED``) for ``/intake``
    rather than a fabricated ``200``. Recorded as an ``INFORMATIONAL`` finding
    so the plan captures the verified-compliant outcome and guards against a
    regression to a fake success.
  * **2.2 / 2.4 — outcome→status mapping (gap closed here).** Before this task,
    every handler hard-coded its HTTP status literals, so the
    "success→2xx / failure→matching-4xx-or-5xx" contract lived only in review
    convention. A single mapping (:mod:`cna.api_status`) now owns status
    selection and every handler routes through it, so no handler can return a
    ``200`` on an error path. Recorded as a ``LOW`` residual gap that this task
    remediates.

  * **2.5 — worker retirement decision (retired).** The ``apps/cna-worker``
    placeholder was a run-once script that stubbed the publish job against a
    hardcoded ``sample-engagement``. The ``apps/cna-api`` ``POST /publish``
    endpoint now does that job for real (real deliverables -> private
    per-engagement blob container -> portal generation -> TTL-capped SAS URL)
    and its docstring states it supersedes the placeholder. The decision was
    **retire** (not retained with a responsibility), approved by the owner as
    REVIEW.md R-016. This repository's half removes the worker's code,
    Dockerfile, image build, manifest keys, dependency group and container
    audit. Both appliance repositories drop the worker
    service from their Terraform ``compute`` modules and deploy workflows in
    the same coordinated change set (TODO.md T-725; REVIEW.md R-016). Recorded as an
    ``INFORMATIONAL`` finding.

These records are consumed by the consolidation step (spec task 14.1).
"""

from __future__ import annotations

from cna.review.model import Finding, Severity

_AREA = "python-engine-api"


def python_engine_api_findings() -> list[Finding]:
    """Return the Requirement 2 findings recorded for this area."""
    return [
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified compliant: /intake returns an honest 501 "
                "(Outcome.NOT_IMPLEMENTED), not a fabricated 200. Keep the "
                "status wired through cna.api_status so it cannot regress to a "
                "fake success."
            ),
            dedup_key="python-engine-api:intake-honest-501",
            subject="apps/cna-api/main.py::intake",
        ),
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "Introduce a single outcome→status mapping (cna.api_status) so "
                "success maps to 2xx and every failure to the matching 4xx/5xx; "
                "route all API handlers through it so no handler returns 200 on "
                "an error path."
            ),
            dedup_key="python-engine-api:single-outcome-status-mapping",
            subject="apps/cna-api",
        ),
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "apps/cna-worker retired: the run-once placeholder "
                "(hardcoded sample-engagement) was superseded by the "
                "apps/cna-api POST /publish endpoint. The worker code, its "
                "Dockerfile, image build and manifest keys are removed from the "
                "core; both appliances drop the worker service from their "
                "Terraform compute modules and deploy workflows in the same "
                "coordinated change set (TODO.md T-725; REVIEW.md R-016)."
            ),
            dedup_key="python-engine-api:worker-retirement",
            subject="apps/cna-worker",
        ),
    ]
