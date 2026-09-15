# Design Document

## Overview

This design describes how the CNA production-hardening review (`production-readiness`) is
organized and executed. It is not a single feature but a coordinated review-and-remediation
effort: specialized reviewers each own an area of the platform, audit it against production best
practices, feed findings into one consolidated and deduplicated `Remediation_Plan`, apply
best-practice fixes aggressively, and escalate — rather than attempt — anything that crosses a
human-gated blocker recorded in `REVIEW.md`.

The design is deliberately structured so that the downstream `tasks.md` can map cleanly: there is
one owner area per section, each with a defined scope, review methodology, verification strategy,
and escalation boundary. Azure and AWS are treated with equal priority. The AWS path is
audited and corrected as far as engineering allows but is never applied live, because its
prerequisites (`REVIEW.md` R-001 through R-006) are externally owned.

**Primary language:** Python (the `cna` core engine, `apps/cna-api`, review tooling, verification
scripts). **Secondary:** TypeScript/Next.js (`apps/cna-web`) and Terraform/HCL
(`infra/terraform`).

### Grounding against current repository state

An important design constraint discovered during audit: the repository already reflects many of
the fixes the acceptance criteria describe. The review is therefore a **verify-then-close-gaps**
process, not a green-field remediation. Reviewers must confirm current state before recording a
finding, so the `Remediation_Plan` records real residual gaps and explicit "verified compliant"
outcomes rather than re-proposing work already done. Examples confirmed during audit:

- `apps/cna-api/main.py` `/intake` already returns an honest `501` (not a fake `200`), and the
  publish endpoint explicitly supersedes the `cna-worker` placeholder.
- The root `Dockerfile` is multi-stage, digest-pinned, runs as non-root `cna:1001`, and has a
  `HEALTHCHECK`.
- `pyproject.toml` declares `cna = "cna.cli.main:cli"`, pinned dependency bounds, and an 80%
  coverage gate.
- The AWS and Azure Terraform each expose the same eight module boundaries
  (`ai, compute, database, identity, observability, runtime, security, storage`).

The review confirms these hold, records any regression as a finding, and focuses effort on
genuine residual gaps and the raw-SDK-passthrough / error-path-status class of correctness issue
the API criteria target.

## Architecture

### Review pipeline

The review runs as a four-stage pipeline that all nine owner areas feed into:

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                     AUDIT (per area)                        │
                 │  9 area reviewers run their methodology + verification      │
                 │  and emit raw Finding records                               │
                 └───────────────────────────┬─────────────────────────────── ┘
                                             │ raw findings (severity, area, action, dedup key,
                                             │               optional blocker id)
                                             ▼
                 ┌──────────────────────────────────────────────────────────┐
                 │                 CONSOLIDATE                                 │
                 │  • merge findings sharing a dedup key into one entry        │
                 │    (referenced-areas = union of contributors)               │
                 │  • classify: fixable vs Escalation_Record (blocker id)      │
                 │  • order by severity → single Remediation_Plan              │
                 └───────────────────────────┬───────────────────────────────┘
                                             │ Remediation_Plan
                            ┌────────────────┴─────────────────┐
                            ▼                                   ▼
                 ┌────────────────────┐            ┌────────────────────────────┐
                 │   APPLY (fixable)   │            │   ESCALATE (gated)          │
                 │  aggressive fixes   │            │  record Escalation_Record   │
                 │  + refactors, then  │            │  referencing REVIEW.md      │
                 │  per-area verify    │            │  R-0NN — no automated action │
                 └────────────────────┘            └────────────────────────────┘
```

## Data Models

### Data model

The review's artifacts are the `Remediation_Plan` and its entries. Modeled as plain records
(Python dataclasses in review tooling; the same shape is what `tasks.md` entries reference):

```python
from dataclasses import dataclass, field
from enum import IntEnum

class Severity(IntEnum):
    INFORMATIONAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

# The nine fixed owner areas — the closed set every finding's area is drawn from.
AREAS = {
    "app-typescript",       # apps/cna-web (Next.js, incl. AWS-shaped UI views)
    "python-engine-api",    # cna/ core + apps/cna-api + apps/cna-worker decision
    "terraform-azure",      # infra/terraform .../azure
    "terraform-aws",        # infra/terraform .../aws (8 modules)
    "cicd",                 # .github/workflows (14)
    "security-secrets",     # detect-secrets, gitleaks, pip-audit, npm audit
    "containers-packaging", # Dockerfiles, docker-compose, cna CLI packaging
    "observability",        # structured logging, AI-path coverage
    "documentation",        # README/CHANGELOG/TODO accuracy, executable paths
}

@dataclass
class Finding:
    area: str                      # ∈ AREAS
    severity: Severity
    proposed_action: str           # non-empty
    dedup_key: str                 # findings sharing this describe one defect
    subject: str                   # the file/module/workflow the finding is about
    blocker_id: str | None = None  # set iff this maps to a REVIEW.md blocker (R-0NN)

@dataclass
class PlanEntry:
    dedup_key: str
    severity: Severity             # max severity among merged findings
    proposed_action: str
    referenced_areas: set[str]     # union of contributing areas
    subjects: set[str]
    is_escalation: bool            # True ⇒ blocker_id required, no automated fix
    blocker_id: str | None = None  # required iff is_escalation

@dataclass
class RemediationPlan:
    entries: list[PlanEntry] = field(default_factory=list)  # ordered severity-desc
```

### Blocker model (`REVIEW.md`)

The set of human-gated blockers and their status is read from `REVIEW.md`. What matters to the
design is the **subject → blocker → status** mapping. Current state:

| Blocker | Subject class | Status | Consumers in this review |
|---|---|---|---|
| R-001 | AWS account / admin access | Open | Terraform AWS, CI/CD |
| R-002 | Terraform S3 state backend + lock | Open | Terraform AWS |
| R-003 | GitHub OIDC deploy role in CI | Open | CI/CD (workflow 212) |
| R-004 | ACM certs + custom-domain decision | Open | Terraform AWS |
| R-005 | Bedrock model access opt-in | Open | Terraform AWS (ai), Observability (AI path) |
| R-006 | Runtime secrets supplied at deploy | Open | Security & secrets, Terraform AWS |
| R-007 | Azure provider registration | **Resolved (not closed)** | Terraform Azure — subject out of scope until CLOSED |
| R-008 | Live Azure beta acceptance sign-off | Open | Terraform Azure |
| R-009 | GitHub Wiki write access | Open (not blocking) | Documentation |

A blocker returns its subject to automated scope **only when its status is CLOSED** — a
`resolved` label alone is not sufficient. R-007 is marked resolved but not closed, so its subject
(Azure provider registration) remains out of automated scope. This closed-status rule drives the
scope-gate behavior (Requirement 10.3).

## Components and Interfaces

Each owner area is a component with: **scope**, **review methodology**, **verification strategy**,
and **escalation boundary**. Fixes are applied aggressively (including refactors) inside the
boundary; anything past it becomes an `Escalation_Record`.

### 1. App / TypeScript — `apps/cna-web`

**Scope.** The Next.js/TypeScript front end, including the AWS-shaped UI views that currently
mirror the Azure deployment model.

**Methodology.** Static review of TypeScript for type-safety gaps, unhandled promise rejections,
and error boundaries; review of the AWS views against the AWS deployment model (Requirement 4.4);
review of API-call error handling so client-facing surfaces do not render raw backend detail.

**Verification.** `npm run lint`, `npm run build` (type-check + production build) in
`apps/cna-web`; `tsc --noEmit` where a standalone type-check is faster.

**Escalation boundary.** UI alignment that depends on the live AWS deployment shape (endpoints,
domains) references R-001/R-004; nothing here performs a deploy.

### 2. Python engine + API — `cna/`, `apps/cna-api`, `apps/cna-worker`

**Scope.** The core `cna` package, the FastAPI API, and the worker retirement decision. This is
the highest-value correctness area and the primary target of Requirement 2.

**Methodology.**
- **`/intake` honesty (2.1):** confirm the endpoint reflects the real result. Current code returns
  `501` (not-implemented) rather than a fabricated success — record as verified compliant, and
  guard against regression to a fake `200`.
- **Error-path status codes (2.2, 2.4):** audit every handler so failures map to the correct
  4xx/5xx class and successes to 2xx. Introduce/confirm a single outcome→status mapping so no
  handler returns `200` on an error path.
- **Raw SDK passthrough (2.3):** audit handlers that surface downstream SDK (`boto3`,
  `azure-*`, `psycopg2`) exceptions; ensure a sanitizer converts them to a generic category
  message with no raw exception text, and log the detail server-side only.
- **Worker retirement (2.5):** the publish endpoint already supersedes `apps/cna-worker`. Record
  a `Remediation_Plan` entry stating the worker is **retired** (or retained with a defined
  responsibility), and carry the corresponding removal/retention action.

**Verification.** `ruff check cna apps`, `ty check cna`, `pytest` with the 80% coverage gate
(`pyproject.toml` `fail_under = 80`), plus FastAPI `TestClient` tests exercising error paths and
sanitization.

**Escalation boundary.** No live database, cloud, or AI calls; SDK behavior is mocked.

### 3. Terraform Azure — `infra/terraform/{providers,environments}/azure`

**Scope.** All eight Azure module boundaries and the dev/prod environments.

**Methodology.** Best-practice audit (tags, diagnostic settings, network exposure, SKU tiers);
drift review of the live-but-stale dev environment; a subject is re-included in automated scope
only once its owning blocker is CLOSED — R-007 is resolved but not closed, so its subject stays
out of scope.

**Verification.** `terraform fmt -check`, `terraform init -backend=false`, `terraform validate`
per root; drift via workflows `350-drift-dev.yml` / `360-drift-prod.yml` (live, human-observed).

**Escalation boundary.** Live acceptance sign-off references R-008; drift detection against live
dev requires the live environment and is recorded, not auto-applied.

### 4. Terraform AWS — `infra/terraform/{providers,environments}/aws` (8 modules)

**Scope.** All eight AWS modules (`ai, compute, database, identity, observability, runtime,
security, storage`) and dev/prod platform/workload roots — authored but never applied.

**Methodology.** Best-practice audit across all eight modules; correct everything engineering can
without an account. Map each finding whose remediation needs live account access, an S3 state
backend, an OIDC deploy role, an ACM certificate, Bedrock access, or a runtime secret to the
corresponding blocker R-001–R-006 (Requirement 4.5).

**Verification.** `terraform fmt -check`, `terraform init -backend=false`, `terraform validate`
on every root (backend init skipped because R-002 is open). Because the AWS review process only
runs once an evaluation of the AWS Terraform has occurred (Requirement 4.3), `terraform validate`
is the gate that authorizes the rest of the AWS review. **No live `terraform apply`**
(Requirement 4.6) and no `plan` against a real account.

**Escalation boundary.** R-001 (account), R-002 (state backend), R-003 (OIDC role), R-004
(certs), R-005 (Bedrock), R-006 (runtime secrets). The AWS-shaped web views (4.4) are a fixable
app-area entry, not an escalation.

### 5. CI/CD — `.github/workflows` (14 workflows)

**Scope.** All 14 numbered workflows and the self-hosted runner topology.

**Methodology.** Best-practice audit per workflow; identify every workflow whose sole executor is
the self-hosted runner as a single point of failure with a proposed mitigation (5.2); verify
every third-party `uses:` reference is pinned to a 40-hex commit SHA and record any that is not
(5.3).

**Verification.** `actionlint` across all workflows; a SHA-pinning checker over every `uses:`
line; YAML parse validation.

**Escalation boundary.** Workflow `212-deploy-aws-split.yml` cannot authenticate to AWS without
the externally provisioned OIDC deploy role — record an `Escalation_Record` referencing R-003
(5.4).

### 6. Security & secrets

**Scope.** The full repository tree and dependency manifests.

**Methodology.** Run `detect-secrets` (against `.secrets.baseline`) and `gitleaks`; run
`pip-audit` and `npm audit`. Record each committed-secret finding by **location and key name
only**, never reproducing the value (6.2). Record each reported vulnerability (6.3).

**Verification.** `detect-secrets scan --baseline .secrets.baseline`, `gitleaks detect`,
`pip-audit`, `npm audit --prefix apps/cna-web`.

**Escalation boundary.** Runtime secrets supplied at deploy time by an external owner reference
R-006 (6.4); the review never invents or commits a secret value.

### 7. Containers & packaging

**Scope.** Each service `Dockerfile` (root, `apps/cna-api`, `apps/cna-web`, `apps/cna-worker`),
`docker-compose.yml`, and `cna` CLI packaging.

**Methodology.** Audit each Dockerfile for digest pinning, multi-stage builds, non-root user
(7.4), and healthchecks; confirm a `docker-compose` fallback path for the web service (7.2);
verify the `cna` CLI installs and runs from the packaged distribution (7.3). Recording a
root-user security finding is treated as mandatory: if that record cannot be written, the entire
review process fails rather than continuing with an unrecorded root-user finding (7.5).

**Verification.** `docker build` per image; `hadolint` on each Dockerfile; a packaging check that
builds the wheel, installs it into a clean virtualenv, and runs `cna --help`; a container check
that the final `USER` is non-root.

**Escalation boundary.** Private image pulls needing Docker Hub credentials reference R-006; no
image is pushed to a live registry.

### 8. Observability

**Scope.** Logging/telemetry for the API, web, and core engine, with emphasis on the AI analysis
path (the least-proven capability).

**Methodology.** Audit that errors are captured as **structured** log records with level and
message (8.2); identify the observability coverage the AI path requires (8.3) — trace/span,
token-usage, and fallback-path logging around Bedrock/Azure OpenAI calls.

**Verification.** Unit tests asserting error events produce parseable structured log records;
static review of logging configuration per service.

**Escalation boundary.** AI-path coverage that depends on live Bedrock access references R-005;
the coverage requirement itself is recorded as a fixable plan entry.

### 9. Documentation

**Scope.** `README.md`, `CHANGELOG.md`, `TODO.md`, and area docs, checked against real state.

**Methodology.** Cross-check documented facts (versions, deployment paths, conventions) against
the tree and record inaccuracies (9.1); for each documented deploy path that cannot be executed,
record its executable status (9.2); record an entry for each still-open doc task among T-103,
T-304, T-401 (9.3).

**Verification.** `scripts/validate_documentation_model.py`; link/anchor checks; confirming
documented commands exist and run (e.g. `cna --help`, workflow names).

**Escalation boundary.** Publishing prepared Wiki pages depends on GitHub Wiki write access —
record an `Escalation_Record` referencing R-009 (9.4).

## Consolidation, Deduplication, and Escalation

**Recording.** Each area reviewer emits `Finding` records with `area`, `severity`,
`proposed_action`, `subject`, a `dedup_key` (a normalized description of the underlying defect),
and an optional `blocker_id` when the finding maps to a `REVIEW.md` blocker.

**Deduplication (1.5).** Findings sharing a `dedup_key` collapse into one `PlanEntry` whose
`referenced_areas` is the union of contributing areas and whose `severity` is the maximum among
them. Consolidation is idempotent — consolidating an already-consolidated plan changes nothing.

**Ordering (1.4).** Entries are sorted by `severity` descending into the single
`Remediation_Plan`.

**Audit completion gating (1.3).** An area audit is not marked complete until its findings have
been successfully recorded. If recording fails, the area audit stays incomplete rather than
reporting a false completion, so a completed audit always implies its findings reached the plan.

**Escalation classification (1.6, 4.5, 10.2, 10.4).** A finding whose subject is owned by a
blocker that is not CLOSED, or whose remediation would require a live deploy / secret
provisioning / account setup, becomes an `Escalation_Record`: `is_escalation = True` with a
required non-empty `blocker_id` drawn from the `R-0NN` set. No automated fix is emitted for it.

**Scope gate (10.1, 10.3).** A blocker whose status is not CLOSED keeps its subject out of
automated scope — even when the blocker is labeled resolved (as R-007 is). A subject returns to
automated scope only once its owning blocker's status is CLOSED. The gate is a pure function of
blocker status, so re-running after a status flip is consistent.

## Verification Strategy Summary

| Area | Primary verification commands |
|---|---|
| App/TypeScript | `npm run lint`, `npm run build`, `tsc --noEmit` (in `apps/cna-web`) |
| Python engine + API | `ruff check`, `ty check cna`, `pytest` (80% gate), FastAPI `TestClient` |
| Terraform Azure | `terraform fmt -check`, `init -backend=false`, `validate`; drift workflows |
| Terraform AWS | `terraform fmt -check`, `init -backend=false`, `validate` (no apply/plan) |
| CI/CD | `actionlint`, SHA-pin checker, YAML parse |
| Security & secrets | `detect-secrets`, `gitleaks`, `pip-audit`, `npm audit` |
| Containers & packaging | `docker build`, `hadolint`, wheel install + `cna --help`, non-root `USER` check |
| Observability | structured-log unit tests, logging-config review |
| Documentation | `validate_documentation_model.py`, link/anchor + command checks |

All verification is local and non-destructive. No command in this review deploys to a live cloud,
provisions a secret, or runs `terraform apply`.

## Error Handling

- **API correctness path.** A single outcome→status mapping guarantees success → 2xx and failure
  → the matching 4xx/5xx; a sanitizer strips raw SDK detail from client responses while logging
  it server-side. This is the behavioral core of Requirement 2.
- **Review tooling.** A failing verification command (e.g. `terraform validate` error, failing
  test) is itself recorded as a `Finding`, not swallowed. A missing tool is recorded as a
  gap in coverage rather than passing silently.
- **Fail-hard on unrecordable root-user finding.** Recording a root-user security finding is a
  mandatory operation. If that record cannot be persisted, the review process fails as a whole
  rather than proceeding with the finding unrecorded (Requirement 7.5). This is the one recording
  failure that aborts the review instead of degrading to a coverage gap.
- **Audit completion depends on recording.** An area audit is marked complete only after its
  findings are successfully recorded; a recording failure leaves the audit incomplete rather than
  falsely complete (Requirement 1.3).
- **Escalation over failure.** When a remediation would cross a human-gated boundary, the process
  stops and records an `Escalation_Record` rather than attempting and failing an unauthorized
  action (Requirement 10.2).

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a
system — a formal statement about what the system should do. Properties bridge human-readable
specifications and machine-verifiable correctness guarantees.*

### Property 1: Finding records are well-formed

*For any* `Finding` produced by any area reviewer, the record has a valid severity, an `area`
drawn only from the nine fixed owner areas, and a non-empty `proposed_action`.

**Validates: Requirements 1.2**

### Property 2: Area coverage is complete

*For any* completed review, the consolidated `Remediation_Plan` represents every subject in each
area's fixed expected set — the nine owner areas overall, the eight AWS module boundaries
(`ai, compute, database, identity, observability, runtime, security, storage`), all 14 CI
workflows, and every service Dockerfile plus `docker-compose.yml`.

**Validates: Requirements 1.1, 4.1, 5.1, 7.1**

### Property 3: The plan is ordered by severity

*For any* set of findings, consolidating them yields a `Remediation_Plan` whose entries are in
non-increasing severity order.

**Validates: Requirements 1.4**

### Property 4: Deduplication is a union and is idempotent

*For any* set of findings, all findings sharing a `dedup_key` collapse into exactly one
`PlanEntry` whose `referenced_areas` equals the union of the contributing areas; and consolidating
an already-consolidated plan produces the same plan.

**Validates: Requirements 1.5**

### Property 5: Escalations carry a valid owning blocker id

*For any* `Remediation_Plan`, every entry marked as an `Escalation_Record` carries a non-empty
`blocker_id` matching the `R-0NN` pattern and present in `REVIEW.md`, and no fixable entry carries
a blocker id.

**Validates: Requirements 1.6, 10.4**

### Property 6: Gated dependencies become escalations

*For any* finding whose subject is owned by an open `REVIEW.md` blocker, or whose remediation
requires a live deploy, secret provisioning, or account setup, the resulting plan entry is an
`Escalation_Record` (never an emitted fix).

**Validates: Requirements 4.5, 10.1, 10.2**

### Property 7: AWS gated dependencies map to R-001 through R-006

*For any* AWS Terraform finding whose remediation depends on live account access, a state
backend, an OIDC deploy role, a certificate, Bedrock model access, or a runtime secret, the plan
entry is an escalation whose `blocker_id` is within R-001 through R-006 and matches the dependency
kind.

**Validates: Requirements 4.5**

### Property 8: Blocker scope gate is consistent with closed status

*For any* blocker, while its status is not CLOSED no fixable action targets a subject it owns
(even when the blocker is labeled resolved), and only once its status is CLOSED is its subject no
longer forced to escalation.

**Validates: Requirements 10.1, 10.3**

### Property 9: No live AWS apply is emitted

*For any* AWS remediation action set produced by the review, no action has a live-apply (or live
account `plan`) action type.

**Validates: Requirements 4.6**

### Property 10: Request outcomes map to the correct HTTP status class

*For any* API request outcome, a successful outcome maps to a 2xx status and a failed outcome maps
to a 4xx or 5xx status whose class matches the failure category (client error → 4xx, server or
downstream error → 5xx).

**Validates: Requirements 2.2, 2.4**

### Property 11: Downstream SDK errors are sanitized

*For any* raw downstream SDK exception text, the client-facing error response excludes the raw
exception text and contains only a generic category message.

**Validates: Requirements 2.3**

### Property 12: Secret findings are recorded without the value

*For any* detected committed secret, the recorded `Remediation_Plan` entry contains the secret's
location and key name and does not contain the raw secret value.

**Validates: Requirements 6.2**

### Property 13: Self-hosted-only workflows are flagged as SPOFs

*For any* CI workflow whose set of runners is exactly the self-hosted runner, the review records a
`Remediation_Plan` entry identifying the single point of failure and carrying a proposed
mitigation.

**Validates: Requirements 5.2**

### Property 14: Third-party action references must be SHA-pinned

*For any* workflow `uses:` reference to a third-party action, the SHA-pin checker records the
reference exactly when it is not pinned to a 40-hex commit SHA.

**Validates: Requirements 5.3**

### Property 15: Root-running images are flagged for non-root

*For any* service Dockerfile whose effective final `USER` is root or unset, the review records a
`Remediation_Plan` entry to run the process as a non-root user, and does not record one when the
final `USER` is a non-root user.

**Validates: Requirements 7.4**

### Property 16: Emitted errors are captured as structured logs

*For any* error event emitted by a reviewed service, the produced log record parses as a
structured record carrying at least a level and a message field.

**Validates: Requirements 8.2**

## Testing Strategy

**Dual approach.** Property-based tests cover the universal invariants above (consolidation,
ordering, dedup, escalation classification, status mapping, sanitization, SHA-pinning, non-root
detection, structured logging). Example and integration tests cover the specific, non-varying
criteria: the `/intake` honest-status behavior (2.1), the worker retirement decision (2.5), the
R-008/R-003/R-006/R-009 escalation entries, the AWS-view alignment entry (4.4), the AI-path
coverage entry (8.3), the open doc-task entries (9.3), and the executable-status entries (9.2).

**Integration/smoke checks** (not property tests) cover the external-tool verifications:
`terraform validate` per root, `detect-secrets`/`gitleaks`/`pip-audit`/`npm audit` scans, the
wheel-install + `cna --help` packaging check, and `docker build`. These are deterministic given
the tree and run 1–N times (one per subject), not 100 iterations.

**Property test configuration.** Each property test runs a minimum of 100 iterations and is tagged
**Feature: production-readiness, Property {number}: {property_text}**, referencing the property it
validates.
