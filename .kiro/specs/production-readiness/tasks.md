# Implementation Plan: Production Readiness Review

## Overview

This plan implements the CNA production-hardening review as a **verify-then-close-gaps** effort.
The codebase already reflects many target fixes, so tasks confirm current state first, close only
genuine residual gaps, and record escalations for human-gated `REVIEW.md` blockers rather than
attempting gated actions.

The work is organized so each of the nine owner areas can be executed by a specialized reviewer.
All areas feed the four-stage pipeline: **AUDIT** (per area, emit `Finding` records) →
**CONSOLIDATE** (dedup + order into one `Remediation_Plan`) → **APPLY** (fixable) /
**ESCALATE** (gated). Shared review tooling (the `Finding`/`PlanEntry`/`RemediationPlan` data
model and consolidation logic) is built first because every area emits into it, and the
property-based tests validate its invariants.

Tasks that depend on an **open** blocker (R-001–R-006, R-008, R-009) are **escalation-only**: they
record an `Escalation_Record` and MUST NOT perform a live apply, deploy, secret provisioning, or
account setup. A blocker's subject returns to automated scope only when its status is CLOSED;
R-007 is resolved but not closed, so its subject (Azure provider registration) stays OUT of
automated scope.

## Tasks

- [x] 1. Establish review tooling: data model and consolidation engine
  - [x] 1.1 Implement the review data model
    - Create `Severity` IntEnum and the `AREAS` closed set (nine owner areas)
    - Implement `Finding`, `PlanEntry`, and `RemediationPlan` dataclasses matching the design shape
    - Enforce well-formedness on construction: valid severity, `area ∈ AREAS`, non-empty `proposed_action`
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Write property test for Finding well-formedness
    - **Property 1: Finding records are well-formed**
    - **Validates: Requirements 1.2**

  - [x] 1.3 Implement the consolidation engine
    - Merge findings sharing a `dedup_key` into one `PlanEntry` (`referenced_areas` = union, `severity` = max)
    - Order entries by severity descending; make consolidation idempotent
    - Classify entries: fixable vs `Escalation_Record` (blocker-owned or gated remediation)
    - _Requirements: 1.3, 1.4, 1.5, 1.6_

  - [x] 1.4 Write property test for severity ordering
    - **Property 3: The plan is ordered by severity**
    - **Validates: Requirements 1.4**

  - [x] 1.5 Write property test for deduplication union + idempotence
    - **Property 4: Deduplication is a union and is idempotent**
    - **Validates: Requirements 1.5**

- [x] 2. Implement the blocker model and scope gate
  - [x] 2.1 Implement `REVIEW.md` blocker parsing and the scope gate
    - Parse the subject → blocker → status mapping (R-001–R-009) from `REVIEW.md`
    - Implement the scope gate: open blocker forces its subject to escalation; a blocker whose status is CLOSED returns its subject to scope; a not-closed blocker (even if labeled resolved, e.g. R-007) keeps its subject out of scope
    - Emit an `Escalation_Record` with a required `blocker_id` for gated findings; forbid blocker ids on fixable entries
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 2.2 Write property test for escalation blocker id validity
    - **Property 5: Escalations carry a valid owning blocker id**
    - **Validates: Requirements 1.6, 10.4**

  - [x] 2.3 Write property test for gated-dependency escalation
    - **Property 6: Gated dependencies become escalations**
    - **Validates: Requirements 4.5, 10.1, 10.2**

  - [x] 2.4 Write property test for scope-gate consistency with status
    - **Property 8: Blocker scope gate is consistent with status**
    - **Validates: Requirements 10.1, 10.3**

- [x] 3. Checkpoint - review tooling
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Python engine + API area review (`cna/`, `apps/cna-api`, `apps/cna-worker`)
  - [x] 4.1 Implement the outcome→status mapping and verify `/intake` honesty
    - Confirm `/intake` returns an honest `501` (not a fake `200`); record verified-compliant and guard against regression
    - Introduce/confirm a single outcome→status mapping so no handler returns `200` on an error path (success→2xx, failure→matching 4xx/5xx)
    - Emit `Finding` records for any residual gap
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 4.2 Write property test for HTTP status class mapping
    - **Property 10: Request outcomes map to the correct HTTP status class**
    - **Validates: Requirements 2.2, 2.4**

  - [x] 4.3 Implement the downstream SDK error sanitizer
    - Audit handlers that surface `boto3`/`azure-*`/`psycopg2` exceptions
    - Convert raw SDK exceptions to a generic category message client-side; log raw detail server-side only
    - _Requirements: 2.3_

  - [x] 4.4 Write property test for SDK error sanitization
    - **Property 11: Downstream SDK errors are sanitized**
    - **Validates: Requirements 2.3**

  - [x] 4.5 Record the worker retirement decision
    - Confirm the publish endpoint supersedes `apps/cna-worker`
    - Record a `Remediation_Plan` entry stating the worker is retired (or retained with a defined responsibility) and carry the removal/retention action
    - _Requirements: 2.5_

  - [x] 4.6 Write error-path and worker-decision tests (FastAPI TestClient)
    - Exercise error paths and sanitization via `TestClient`; assert the worker-retirement entry (2.1, 2.5)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 4.7 Verify Python area
    - Run `ruff check cna apps`, `ty check cna`, `pytest` with the 80% coverage gate; record failures as `Finding` records
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 5. App / TypeScript area review (`apps/cna-web`)
  - [x] 5.1 Audit TypeScript for type-safety and error handling
    - Static review for type-safety gaps, unhandled promise rejections, missing error boundaries
    - Ensure API-call error handling does not render raw backend detail to client surfaces
    - Emit `Finding` records for residual gaps
    - _Requirements: 1.1, 1.2_

  - [x] 5.2 Record AWS-view alignment entry
    - Review AWS-shaped UI views against the AWS deployment model; record a `Remediation_Plan` entry to align each view (fixable app-area entry, not an escalation)
    - _Requirements: 4.4_

  - [x] 5.3 Verify web area
    - Run `npm run lint` and `npm run build` (type-check + production build) in `apps/cna-web`; `tsc --noEmit` where faster; record failures as findings
    - _Requirements: 1.1, 1.2_

- [x] 6. Terraform Azure area review (`infra/terraform/{providers,environments}/azure`)
  - [x] 6.1 Audit and correct Azure Terraform across all eight modules
    - Best-practice audit (tags, diagnostic settings, network exposure, SKU tiers) across `ai, compute, database, identity, observability, runtime, security, storage`
    - Re-include subjects only once their blocker status is CLOSED (R-007 is resolved but not closed, so its subject stays out of scope); apply fixable corrections; record drift of the live-but-stale dev environment as a `Remediation_Plan` entry
    - _Requirements: 3.1, 3.3_

  - [x] 6.2 Verify Azure Terraform and record R-008 escalation
    - Run `terraform fmt -check`, `terraform init -backend=false`, `terraform validate` per root; record results
    - Record an `Escalation_Record` referencing R-008 for live acceptance sign-off (escalation-only, no live apply)
    - _Requirements: 3.2, 3.4_

- [x] 7. Terraform AWS area review (`infra/terraform/{providers,environments}/aws`, 8 modules)
  - [x] 7.1 Audit and correct AWS Terraform across all eight modules
    - Best-practice audit across `ai, compute, database, identity, observability, runtime, security, storage` and dev/prod roots
    - Apply every correction engineering allows without an account; emit `Finding` records
    - _Requirements: 4.1_

  - [x] 7.2 Verify AWS Terraform (no live apply/plan) and map gated findings to R-001–R-006
    - Run `terraform fmt -check`, `terraform init -backend=false`, `terraform validate` on every root (backend init skipped, R-002 open); record results
    - Map each finding needing account access / state backend / OIDC role / cert / Bedrock / runtime secret to its blocker (R-001–R-006) as an escalation-only entry; emit NO live `apply` or account `plan`
    - _Requirements: 4.2, 4.3, 4.5, 4.6_

  - [x] 7.3 Write property test for AWS gated → R-001..R-006 mapping
    - **Property 7: AWS gated dependencies map to R-001 through R-006**
    - **Validates: Requirements 4.5**

  - [x] 7.4 Write property test for no live AWS apply emitted
    - **Property 9: No live AWS apply is emitted**
    - **Validates: Requirements 4.6**

- [x] 8. Checkpoint - infrastructure areas
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. CI/CD area review (`.github/workflows`, 14 workflows)
  - [x] 9.1 Audit all 14 workflows and flag self-hosted SPOFs
    - Best-practice audit per workflow; identify each workflow whose sole executor is the self-hosted runner and record a `Remediation_Plan` entry with a proposed mitigation
    - _Requirements: 5.1, 5.2_

  - [x] 9.2 Write property test for self-hosted-only SPOF flagging
    - **Property 13: Self-hosted-only workflows are flagged as SPOFs**
    - **Validates: Requirements 5.2**

  - [x] 9.3 Implement the SHA-pin checker and record R-003 escalation
    - Verify every third-party `uses:` reference is pinned to a 40-hex commit SHA; record any that is not
    - Record an `Escalation_Record` referencing R-003 for `212-deploy-aws-split.yml` (cannot authenticate without the external OIDC deploy role) — escalation-only
    - _Requirements: 5.3, 5.4_

  - [x] 9.4 Write property test for third-party action SHA-pinning
    - **Property 14: Third-party action references must be SHA-pinned**
    - **Validates: Requirements 5.3**

  - [x] 9.5 Verify CI/CD area
    - Run `actionlint` across all workflows and YAML parse validation; record failures as findings
    - _Requirements: 5.1_

- [x] 10. Security & secrets area review
  - [x] 10.1 Run secret and dependency scans and record findings
    - Run `detect-secrets scan --baseline .secrets.baseline` and `gitleaks detect`; record each committed-secret finding by location and key name only, never the value
    - Run `pip-audit` and `npm audit --prefix apps/cna-web`; record each reported vulnerability
    - Record an `Escalation_Record` referencing R-006 for runtime secrets supplied at deploy time — never invent or commit a secret value (escalation-only)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 10.2 Write property test for secret findings recorded without value
    - **Property 12: Secret findings are recorded without the value**
    - **Validates: Requirements 6.2**

- [x] 11. Containers & packaging area review
  - [x] 11.1 Audit Dockerfiles, compose, and CLI packaging
    - Audit each `Dockerfile` (root, `apps/cna-api`, `apps/cna-web`, `apps/cna-worker`) and `docker-compose.yml` for digest pinning, multi-stage builds, healthchecks
    - Detect any image whose effective final `USER` is root/unset and record a non-root `Remediation_Plan` entry; confirm a `docker-compose` web fallback path
    - If recording a root-user finding fails, fail the entire review process (7.5)
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [x] 11.2 Write property test for root-running image flagging
    - **Property 15: Root-running images are flagged for non-root**
    - **Validates: Requirements 7.4**

  - [x] 11.3 Verify container builds and CLI packaging
    - Run `docker build` per image and `hadolint` on each Dockerfile; build the wheel, install into a clean virtualenv, run `cna --help`; assert final `USER` is non-root
    - Private-image-pull credentials reference R-006 (escalation-only); no image is pushed to a live registry
    - _Requirements: 7.1, 7.3, 7.4_

- [x] 12. Observability area review
  - [x] 12.1 Audit structured logging and record AI-path coverage entry
    - Audit that errors are captured as structured log records with level and message across API, web, and core engine
    - Record a `Remediation_Plan` entry identifying the AI-path observability coverage (trace/span, token-usage, fallback logging); coverage that depends on live Bedrock references R-005 (escalation-only)
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 12.2 Write property test for structured-log capture
    - **Property 16: Emitted errors are captured as structured logs**
    - **Validates: Requirements 8.2**

- [x] 13. Documentation area review
  - [x] 13.1 Audit documentation accuracy and executable paths, record open doc tasks
    - Cross-check documented facts (versions, deployment paths, conventions) against the tree; record inaccuracies
    - Record the executable status of each documented deploy path that cannot be executed; record a `Remediation_Plan` entry for each still-open doc task among T-103, T-304, T-401
    - Record an `Escalation_Record` referencing R-009 for Wiki publication (escalation-only)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 13.2 Verify documentation model
    - Run `scripts/validate_documentation_model.py`, link/anchor checks, and confirm documented commands run (e.g. `cna --help`, workflow names); record failures as findings
    - _Requirements: 9.1, 9.2_

- [x] 14. Consolidate all findings into the single Remediation_Plan
  - [x] 14.1 Run consolidation across all nine areas and assert coverage
    - Feed every area's `Finding` records through the consolidation engine into one severity-ordered `Remediation_Plan`
    - Assert coverage: nine owner areas, eight AWS modules, all 14 CI workflows, every service Dockerfile plus `docker-compose.yml`
    - _Requirements: 1.1, 1.4, 1.5, 4.1, 5.1, 7.1_

  - [x] 14.2 Write property test for complete area coverage
    - **Property 2: Area coverage is complete**
    - **Validates: Requirements 1.1, 4.1, 5.1, 7.1**

  - [x] 14.3 Wire escalations into the Remediation_Plan
    - Ensure every escalation entry (R-001–R-006, R-008, R-009 consumers) carries its owning `blocker_id`; assert no fixable entry carries a blocker id
    - _Requirements: 1.6, 10.4_

- [x] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (property-based and supplementary tests) and can be skipped
  for a faster MVP; each references a specific property or requirement for traceability.
- Escalation-only tasks (6.2, 7.2, 9.3, 10.1, 11.3, 12.1, 13.1) record an `Escalation_Record`
  referencing the owning `REVIEW.md` blocker and MUST NOT perform a live apply, deploy, secret
  provisioning, or account setup. A subject returns to automated scope only once its owning
  blocker's status is CLOSED; R-007 is resolved but not closed, so Azure provider registration
  stays out of scope.
- This is a verify-then-close-gaps effort: confirm current state (record verified-compliant) before
  recording a finding, so the plan captures real residual gaps rather than re-proposing done work.
- Property tests run a minimum of 100 iterations and are tagged
  **Feature: production-readiness, Property {number}**.
- Integration/smoke verifications (`terraform validate`, `detect-secrets`/`gitleaks`/`pip-audit`/
  `npm audit`, wheel-install + `cna --help`, `docker build`) run once per subject, not 100 iterations.
- All verification is local and non-destructive; no command deploys to a live cloud, provisions a
  secret, or runs `terraform apply`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "4.1", "5.1", "6.1", "7.1", "9.1", "10.1", "11.1", "12.1", "13.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.2", "6.2", "7.2", "9.2", "9.3", "10.2", "11.2", "12.2", "13.2"] },
    { "id": 5, "tasks": ["4.4", "4.5", "5.3", "7.3", "7.4", "9.4", "9.5", "11.3"] },
    { "id": 6, "tasks": ["4.6", "4.7"] },
    { "id": 7, "tasks": ["14.1"] },
    { "id": 8, "tasks": ["14.2", "14.3"] }
  ]
}
```
