# ADR-005: Extract Inline Python from GitHub Actions Workflows to scripts/ci/

**Status:** Accepted  
**Date:** 2026-06-07  
**Deciders:** Platform Engineering  
**Tags:** CI/CD, maintainability, GitHub Actions, YAML

---

## Context

The deployment workflow (`031-deploy-azure.yml`) originally contained Python logic embedded directly in YAML using the `python - <<'PY'` heredoc pattern:

```yaml
- name: Resolve rollback targets
  run: |
    python - <<'PY'
    import json
    import os
    ...
    PY
```

This approach produces a YAML parse error. The YAML specification requires that content in a literal block scalar (`|`) be indented relative to its parent key. When the Python heredoc delimiter (`<<'PY'`) is present and the script body begins at column 0 (no indentation), YAML parsers interpret `import json` as a top-level mapping key expecting a `:` separator and fail.

Additionally, inline Python in YAML has significant maintainability drawbacks:
- No syntax highlighting in editors (the script is treated as a string)
- No ability to lint, format, or unit-test the script independently
- Difficult to reuse the logic across multiple workflows or jobs
- Diff noise in pull requests — a single-line Python change is buried in YAML context

Three Python blocks were embedded in the deploy workflow: rollback target resolution, apply evidence update, and deployment evidence evaluation.

## Decision

Extract all Python scripts to standalone files under `scripts/ci/`:

| Original inline location | Extracted file |
|---|---|
| Rollback target resolution (deploy job) | `scripts/ci/resolve_rollback_target.py` |
| Apply evidence update (apply job) | `scripts/ci/update_apply_evidence.py` |
| Deployment evidence evaluation (verify job) | `scripts/ci/evaluate_deployment_evidence.py` |

Each script reads inputs exclusively from environment variables (set via the workflow `env:` block) and writes outputs to `$GITHUB_ENV`. No command-line arguments are used. This keeps the workflow step clean:

```yaml
- name: Resolve rollback targets
  env:
    CATALOG_DIR: ${{ github.workspace }}/.deployment-catalog/${{ inputs.environment }}
    GITHUB_ENV: $GITHUB_ENV
  run: python ${{ github.workspace }}/scripts/ci/resolve_rollback_target.py
```

Scripts are co-located in `scripts/ci/` rather than a root `scripts/` directory to distinguish CI-internal tooling from operator scripts (e.g., `Set-CnaRbac.ps1`).

## Consequences

**Positive:**
- YAML parse error is eliminated — the workflow reliably parses and runs
- Each script can be linted with `pylint`/`ruff` and unit-tested with `pytest` independently of the workflow
- Changes to business logic in these scripts produce clean, reviewable diffs
- Scripts are reusable across workflows and environments without copy-paste

**Negative / Risks:**
- The `python` executable must be available in the runner environment. GitHub-hosted `ubuntu-latest` runners include Python 3.x by default — no `setup-python` step is required for these scripts. This assumption should be documented in the script headers.
- Environment variable naming becomes the interface contract between the workflow and the script. Adding a new input requires coordinating a change in both the workflow `env:` block and the script. This is less discoverable than function arguments.
- Scripts checked in to `scripts/ci/` are executable artifacts that run in production CI. They should be treated with the same review rigor as application code.

**Neutral:**
- Step summary Python (`python - <<'PY' >> "$GITHUB_STEP_SUMMARY"`) in other workflows (e.g., test result formatting) is a different pattern — it uses shell redirection rather than a heredoc, and the short scripts involved don't justify extraction. These are left in place.
