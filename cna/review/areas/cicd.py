"""Findings for the ``cicd`` area (Requirement 5 CI/CD resilience).

This is a *verify-then-close-gaps* record for the 14 numbered GitHub Actions
workflows under ``.github/workflows/``. The audit against Requirement 5 covers
runner topology (5.1, 5.2), least-privilege ``permissions`` blocks, concurrency
guards, and per-job timeouts. Third-party action SHA-pinning (5.3) and the
R-003 escalation for ``212-deploy-aws-split.yml`` (5.4) are recorded separately
by spec task 9.3 — this module deliberately records neither so the two tasks do
not double-count.

Runner topology (5.2). The self-hosted runner is the *sole* executor for 13 of
the 14 workflows; only ``370-registry-cleanup.yml`` runs on a GitHub-hosted
runner (``ubuntu-latest``), because the Docker Hub web/API domain WAF-blocks the
self-hosted VPS IP. Every self-hosted-only workflow is therefore a single point
of failure: if the one runner is offline, unregistered, or its host is down,
that workflow cannot execute at all — there is no GitHub-hosted fallback, no
runner matrix, and no documented failover. Each is recorded as a
``Remediation_Plan`` entry (design Property 13) carrying a concrete mitigation.

Best-practice fixes applied in-tree by this task (low-risk, runner-topology
untouched): added ``timeout-minutes`` to jobs that lacked a runaway-billing
guard, and added ``concurrency`` guards to the scheduled/dispatch workflows that
lacked one. Least-privilege ``permissions`` blocks were already present on all
14 workflows and are recorded as verified-compliant.

These records are consumed by the consolidation step (spec task 14.1).
"""

from __future__ import annotations

from cna.review.model import Finding, Severity

_AREA = "cicd"

# The 13 workflows whose sole executor is the self-hosted runner (every job
# declares ``runs-on: self-hosted`` with no GitHub-hosted fallback and no runner
# matrix). ``370-registry-cleanup.yml`` is deliberately absent: it is the one
# workflow pinned to ``ubuntu-latest`` (GitHub-hosted), so it is not a
# self-hosted SPOF. Keep this in sync with a grep over the workflow tree:
#   grep -rL 'runs-on: ubuntu' .github/workflows/*.yml
SELF_HOSTED_ONLY_WORKFLOWS: tuple[str, ...] = (
    "000-bootstrap-backend.yml",
    "100-validate-prereqs.yml",
    "200-build-images.yml",
    "211-deploy-azure-split.yml",
    "212-deploy-aws-split.yml",
    "220-fast-redeploy.yml",
    "300-test-codebase.yml",
    "310-release-version.yml",
    "320-publish-portal.yml",
    "330-teardown.yml",
    "340-sync-keys.yml",
    "350-drift-dev.yml",
    "360-drift-prod.yml",
)

# The one GitHub-hosted workflow — recorded so coverage of all 14 workflows is
# explicit and the "not a SPOF" outcome is captured rather than merely omitted.
GITHUB_HOSTED_WORKFLOWS: tuple[str, ...] = ("370-registry-cleanup.yml",)

# The single self-hosted runner label. A workflow whose executor set is exactly
# this label — no GitHub-hosted fallback and no runner matrix — is a
# single point of failure (design Property 13, Requirement 5.2).
SELF_HOSTED_RUNNER: str = "self-hosted"


def is_self_hosted_spof(runners: set[str]) -> bool:
    """Decide whether a workflow's runner set is a self-hosted single point of failure.

    A workflow is a self-hosted SPOF exactly when its set of runners is exactly
    ``{"self-hosted"}``: the self-hosted runner is the sole executor, with no
    GitHub-hosted fallback and no additional matrix runner to fail over to. An
    empty runner set is not a SPOF (there is no self-hosted executor to lose),
    and any set containing a GitHub-hosted (or any other) runner is not a SPOF
    because that runner provides a fallback path.

    This is the pure decision that :func:`cicd_findings` records over the real
    workflow tree; keeping it separate lets the invariant be tested over
    arbitrary runner sets (design Property 13, Requirement 5.2).
    """
    return runners == {SELF_HOSTED_RUNNER}


def _spof_finding(workflow: str) -> Finding:
    """Record one self-hosted-only workflow as a single-point-of-failure entry.

    The mitigation is deliberately concrete and does not itself change runner
    topology (that is a human/infra decision, not an automated edit): provision
    a second self-hosted runner in the same labelled group (so scheduling load-
    balances and one host failing no longer halts the workflow), or add a
    GitHub-hosted fallback for the jobs that need no VPS-only capability, and
    document the failover procedure.
    """
    return Finding(
        area=_AREA,
        severity=Severity.MEDIUM,
        proposed_action=(
            f"{workflow} runs solely on the self-hosted runner (runs-on: "
            "self-hosted with no GitHub-hosted fallback or runner matrix), so a "
            "single offline/unregistered runner halts it entirely — a single "
            "point of failure. Mitigate by registering a second runner in the "
            "same label group so scheduling load-balances across hosts, and/or "
            "add a GitHub-hosted fallback (runs-on matrix) for jobs that need no "
            "VPS-only capability, and document the failover procedure."
        ),
        dedup_key=f"cicd:self-hosted-spof:{workflow}",
        subject=f".github/workflows/{workflow}",
    )


def cicd_findings() -> list[Finding]:
    """Return the Requirement 5.1/5.2 findings recorded for the CI/CD area."""
    findings: list[Finding] = [_spof_finding(workflow) for workflow in SELF_HOSTED_ONLY_WORKFLOWS]

    # 5.2 counter-case: the one GitHub-hosted workflow is not a SPOF against the
    # self-hosted runner. Recorded as INFORMATIONAL so the plan reflects that all
    # 14 workflows were audited, not only the 13 flagged ones.
    findings.append(
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified: 370-registry-cleanup.yml runs on ubuntu-latest "
                "(GitHub-hosted) by design — the Docker Hub web/API domain "
                "WAF-blocks the self-hosted VPS IP. It is not a self-hosted "
                "single point of failure; no runner-topology change needed."
            ),
            dedup_key="cicd:self-hosted-spof:370-registry-cleanup.yml",
            subject=".github/workflows/370-registry-cleanup.yml",
        )
    )

    # 5.1 best-practice: least-privilege permissions blocks. All 14 workflows
    # already declare an explicit top-level permissions block, so the
    # default-broad GITHUB_TOKEN scope is not in play. Recorded as verified
    # compliant to guard against regression.
    findings.append(
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified compliant: every workflow declares an explicit "
                "least-privilege permissions block (no reliance on the default "
                "broad GITHUB_TOKEN scope). Keep new workflows declaring "
                "permissions explicitly."
            ),
            dedup_key="cicd:least-privilege-permissions",
            subject=".github/workflows",
        )
    )

    # 5.1 best-practice: runaway-billing guard. Several workflows lacked a
    # per-job timeout, so a wedged step could burn self-hosted runner time
    # indefinitely. This task added timeout-minutes to the jobs that lacked one;
    # recorded as a LOW gap this task closes.
    findings.append(
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "Add a per-job timeout-minutes to every workflow job so a wedged "
                "step cannot burn self-hosted runner time indefinitely. Closed by "
                "this task for the jobs that lacked one (000, 100, 200, 211, 212, "
                "220, 330, 340, 350, 360, 370); 300/310/320 already set it."
            ),
            dedup_key="cicd:job-timeouts",
            subject=".github/workflows",
        )
    )

    # 5.1 best-practice: concurrency guards. Deploy/teardown-class and scheduled
    # workflows without a concurrency group can overlap (double drift plans,
    # racing image updates). This task added guards where clearly safe.
    findings.append(
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "Add a concurrency group to workflows that can overlap "
                "(fast-redeploy, sync-keys, drift, release, publish, cleanup, "
                "bootstrap, validate) so a newer run supersedes or serializes an "
                "in-flight one. Closed by this task where clearly safe; 200/211/"
                "212/300/330 already had one."
            ),
            dedup_key="cicd:concurrency-guards",
            subject=".github/workflows",
        )
    )

    return findings


def cicd_verify_findings() -> list[Finding]:
    """Return the Requirement 5.1 CI/CD verification records (spec task 9.5).

    Kept separate from the 9.1 audit findings (:func:`cicd_findings`) and the
    9.3 SHA-pin/escalation records (:mod:`cna.review.areas.cicd_shapin`) so the
    ``actionlint`` + YAML-parse verification is attributable to this task and
    does not double-count. Two records:

      * **actionlint sweep (INFORMATIONAL, verified-compliant).** ``actionlint``
        v1.7.7 linted all 14 workflows under ``.github/workflows/`` with **0
        errors** — confirming the workflow tree, including the ``timeout-minutes``
        and ``concurrency`` blocks added by spec tasks 9.1/9.3 and the SHA-pinned
        ``uses:`` references, is syntactically valid and free of the checks
        actionlint enforces (expression syntax, action/input references, runner
        labels, ``needs`` graph, event triggers). actionlint's optional
        sub-linters ``shellcheck`` (``run:`` shell scripts) and ``pyflakes``
        (inline Python) were unavailable on the verification host and were
        auto-disabled; that deeper ``run:``-body linting is recorded as a
        partial-coverage note, not a failure — every actionlint core rule passed.
        If ``actionlint`` itself were unavailable this would instead be recorded
        as a coverage-gap finding rather than a silent pass.

      * **YAML parse validation (INFORMATIONAL, verified-compliant).** Every one
        of the 14 workflow files parses cleanly via ``yaml.safe_load`` — the
        recent 9.1/9.3 edits left valid YAML with no tab/indentation or
        duplicate-key breakage.

    Both are recorded so the plan reflects that Requirement 5.1's verification
    ran and passed (not merely that nothing broke). These records are consumed
    by the consolidation step (spec task 14.1).
    """
    return [
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified compliant: actionlint v1.7.7 linted all 14 workflows "
                "under .github/workflows/ with 0 errors, confirming the tree — "
                "including the timeout-minutes/concurrency blocks added by tasks "
                "9.1/9.3 and the SHA-pinned uses: references — passes every "
                "actionlint core rule (expression syntax, action/input refs, "
                "runner labels, needs graph, event triggers). actionlint's "
                "optional shellcheck (run: shell) and pyflakes (inline Python) "
                "sub-linters were unavailable on the verification host and were "
                "auto-disabled, so deeper run:-body script linting is partial "
                "coverage; install shellcheck + pyflakes on the CI linter host "
                "(370-registry-cleanup.yml / 300-test-codebase.yml) to close it. "
                "Re-run actionlint on every workflow change and guard against a "
                "lint regression."
            ),
            dedup_key="cicd:actionlint-sweep",
            subject=".github/workflows",
        ),
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified compliant: all 14 .github/workflows/*.yml files parse "
                "cleanly via yaml.safe_load — the timeout-minutes and concurrency "
                "edits from tasks 9.1/9.3 left valid YAML with no indentation, "
                "tab, or duplicate-key breakage. Keep YAML parse validation in "
                "the workflow-lint step and guard against a parse regression."
            ),
            dedup_key="cicd:yaml-parse-validation",
            subject=".github/workflows",
        ),
    ]
