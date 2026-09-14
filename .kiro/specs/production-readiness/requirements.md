# Requirements Document

## Introduction

This feature defines a full production-hardening review of the Cloud Network Assessment (CNA)
platform (v0.8.0b0). Specialized review activities audit every area of the platform — application
and API code, per-cloud infrastructure (Azure and AWS), CI/CD, security and secrets, container
and packaging, observability, and documentation — against production best practices, produce a
prioritized remediation plan, and apply fixes aggressively (including refactors) up to the point
of a truly human-gated blocker.

Azure and AWS are treated with equal priority. Azure has a live (but stale) development
environment; AWS Terraform is authored but never applied and cannot be validated live until the
human-gated account prerequisites recorded in `REVIEW.md` (R-001 through R-006) are cleared. The
human-gated blockers in `REVIEW.md` are explicitly out of scope for automated remediation and are
handled as escalations rather than fixable items.

The platform comprises three containerized services — `apps/cna-web` (Next.js/TypeScript),
`apps/cna-api` (FastAPI/Python), and `apps/cna-worker` (Python placeholder and retirement
candidate) — backed by PostgreSQL, authenticated via Microsoft Entra ID, and driven by the core
`cna` Python package exposed as the `cna` CLI.

## Glossary

- **CNA_Platform**: The complete Cloud Network Assessment system, including all services, the core
  engine, infrastructure, and delivery pipelines.
- **Review_Process**: The production-hardening review activity that audits an area against best
  practices and records findings.
- **Remediation_Plan**: The prioritized, deduplicated list of findings with severity, owner area,
  and proposed action produced by the Review_Process.
- **Web_Service**: The `apps/cna-web` Next.js/TypeScript front-end service.
- **API_Service**: The `apps/cna-api` FastAPI/Python back-end service.
- **Worker_Service**: The `apps/cna-worker` Python placeholder service, a retirement candidate.
- **Core_Engine**: The `cna` Python package installed and exposed as the `cna` CLI.
- **Azure_Infrastructure**: The Terraform-managed Azure deployment under
  `infra/terraform/providers/azure/` and `infra/terraform/environments/azure/`.
- **AWS_Infrastructure**: The Terraform-managed AWS deployment under
  `infra/terraform/providers/aws/` and `infra/terraform/environments/aws/`.
- **CI_Pipeline**: The set of 14 numbered GitHub Actions workflows under `.github/workflows/`.
- **Self_Hosted_Runner**: The self-hosted GitHub Actions runner that executes 13 of the 14
  workflows.
- **Quality_Gate**: An automated check that must pass for a change to be accepted (ruff, ty,
  pytest coverage, detect-secrets, and equivalents).
- **Human_Gated_Blocker**: An item recorded in `REVIEW.md` that requires external approval, a
  credential, an account, an access grant, or a named-owner decision and cannot be resolved by
  engineering work alone.
- **Escalation_Record**: A documented reference that maps a discovered limitation to its owning
  `REVIEW.md` blocker rather than attempting an automated fix.

## Requirements

### Requirement 1: Review coverage and prioritized remediation plan

**User Story:** As a platform maintainer, I want every production-relevant area audited against
best practices and consolidated into a single prioritized plan, so that I can see the full
hardening backlog and its ordering in one place.

#### Acceptance Criteria

1. THE Review_Process SHALL audit each of the following areas against production best practices:
   application and API code, Azure_Infrastructure, AWS_Infrastructure, CI_Pipeline, security and
   secrets, container and packaging, observability, and documentation.
2. WHEN an area audit completes, THE Review_Process SHALL record each finding with a severity, the
   owning area, and a proposed action.
3. WHILE an area audit's findings have not been successfully recorded, THE Review_Process SHALL
   NOT mark the area audit complete.
4. THE Review_Process SHALL consolidate all findings into a single Remediation_Plan ordered by
   severity.
5. IF two or more findings describe the same underlying defect, THEN THE Review_Process SHALL
   record the defect as one Remediation_Plan entry that references each contributing area.
6. WHERE a finding maps to a Human_Gated_Blocker, THE Review_Process SHALL mark the
   Remediation_Plan entry as an Escalation_Record instead of a fixable item.

### Requirement 2: Application and API correctness

**User Story:** As an API consumer, I want the API to report real outcomes with accurate status
codes and sanitized errors, so that I can trust responses and integrate against them safely.

#### Acceptance Criteria

1. WHEN the API_Service receives a request to the `/intake` endpoint, THE API_Service SHALL return
   a response that reflects the actual result of the intake operation.
2. IF a request to the API_Service fails, THEN THE API_Service SHALL return an HTTP status code in
   the 4xx or 5xx range that corresponds to the failure category.
3. WHEN a downstream SDK returns an error to the API_Service, THE API_Service SHALL return a
   sanitized error response that excludes raw SDK exception detail.
4. WHEN the API_Service completes any request successfully, THE API_Service SHALL return an HTTP
   status code in the 2xx range for every such successful outcome.
5. WHERE the Worker_Service is confirmed as a retirement candidate, THE Review_Process SHALL
   record a Remediation_Plan entry stating whether the Worker_Service is retired or retained with
   a defined responsibility.

### Requirement 3: Azure infrastructure hardening

**User Story:** As an infrastructure owner, I want the Azure deployment refreshed and validated
against best practices, so that the development environment is current and deployment-ready.

#### Acceptance Criteria

1. THE Review_Process SHALL audit the Azure_Infrastructure Terraform against production best
   practices and record each finding in the Remediation_Plan.
2. WHEN the Azure_Infrastructure Terraform is evaluated, THE Review_Process SHALL, for every such
   evaluation, run `terraform validate` and record the result.
3. IF the Azure development environment configuration has drifted from the current Terraform
   definition, THEN THE Review_Process SHALL record the drift as a Remediation_Plan entry.
4. WHERE live Azure acceptance sign-off is required for beta exit, THE Review_Process SHALL record
   an Escalation_Record referencing `REVIEW.md` R-008.

### Requirement 4: AWS infrastructure hardening

**User Story:** As an infrastructure owner, I want the authored-but-unapplied AWS Terraform
audited and corrected as far as engineering allows, so that the AWS path is deploy-ready once
account prerequisites clear.

#### Acceptance Criteria

1. THE Review_Process SHALL audit the AWS_Infrastructure Terraform across all eight module
   boundaries against production best practices and record each finding in the Remediation_Plan.
2. WHEN the AWS_Infrastructure Terraform is evaluated, THE Review_Process SHALL run
   `terraform validate` and record the result.
3. WHILE no evaluation of the AWS_Infrastructure Terraform has occurred, THE Review_Process SHALL
   NOT run the AWS_Infrastructure review process.
4. WHERE the AWS UI views in the Web_Service retain an Azure-shaped structure, THE Review_Process
   SHALL record a Remediation_Plan entry to align each view with the AWS deployment model.
5. IF an AWS remediation depends on live account access, a state backend, an OIDC deploy role, a
   certificate, Bedrock model access, or a runtime secret, THEN THE Review_Process SHALL record an
   Escalation_Record referencing the corresponding `REVIEW.md` blocker among R-001 through R-006.
6. THE Review_Process SHALL exclude live `terraform apply` against AWS from the automated
   remediation scope.

### Requirement 5: CI/CD resilience

**User Story:** As a release engineer, I want the delivery pipeline audited for single points of
failure and best-practice gaps, so that builds and deploys remain reliable.

#### Acceptance Criteria

1. THE Review_Process SHALL audit each of the 14 CI_Pipeline workflows against production best
   practices and record each finding in the Remediation_Plan.
2. WHERE the Self_Hosted_Runner is the sole executor for a CI_Pipeline workflow, THE
   Review_Process SHALL record a Remediation_Plan entry identifying the single point of failure
   and a proposed mitigation.
3. WHEN a CI_Pipeline workflow references a GitHub Action, THE Review_Process SHALL verify that
   the Action reference is pinned to a commit SHA and record any reference that is not.
4. IF a CI_Pipeline workflow cannot authenticate to AWS because a deploy role or credential is
   externally provisioned, THEN THE Review_Process SHALL record an Escalation_Record referencing
   `REVIEW.md` R-003.

### Requirement 6: Security and secrets

**User Story:** As a security owner, I want the codebase and pipeline audited for secret exposure
and dependency risk, so that no credential leaks and known vulnerabilities are surfaced.

#### Acceptance Criteria

1. THE Review_Process SHALL run detect-secrets and gitleaks scans across the repository and record
   each finding in the Remediation_Plan.
2. IF a scan detects a committed secret, THEN THE Review_Process SHALL record a Remediation_Plan
   entry that identifies the secret by location and key name without reproducing the secret value,
   regardless of whether the detection is a false positive or a known-safe test secret.
3. THE Review_Process SHALL run pip-audit and npm audit and record each reported vulnerability in
   the Remediation_Plan.
4. WHERE a runtime secret must be supplied at deploy time from an external owner, THE
   Review_Process SHALL record an Escalation_Record referencing `REVIEW.md` R-006.

### Requirement 7: Container and packaging

**User Story:** As a platform operator, I want the container images and local stack audited for
best practices and resilience, so that services build reproducibly and run locally without gaps.

#### Acceptance Criteria

1. THE Review_Process SHALL audit each service Dockerfile and the `docker-compose.yml` definition
   against production container best practices and record each finding in the Remediation_Plan.
2. WHERE the local stack has no docker-compose fallback for the Web_Service, THE Review_Process
   SHALL record a Remediation_Plan entry to add a Web_Service fallback path.
3. WHEN the Core_Engine package is evaluated, THE Review_Process SHALL verify that the `cna` CLI
   installs and runs from the packaged distribution and record the result.
4. IF a container image runs its process as the root user, THEN THE Review_Process SHALL record a
   Remediation_Plan entry to run the process as a non-root user.
5. IF recording a root-user security finding fails, THEN THE Review_Process SHALL fail the entire
   review process.

### Requirement 8: Observability

**User Story:** As an operator, I want the platform's telemetry audited against best practices, so
that production issues are detectable across both clouds.

#### Acceptance Criteria

1. THE Review_Process SHALL audit the observability configuration for the API_Service,
   Web_Service, and Core_Engine against production best practices and record each finding in the
   Remediation_Plan.
2. WHEN a service emits an error, THE Review_Process SHALL verify that the error is captured in a
   structured log record and record any gap in the Remediation_Plan.
3. WHERE the AI analysis path is the least-proven capability, THE Review_Process SHALL record a
   Remediation_Plan entry identifying the observability coverage required for that path.

### Requirement 9: Documentation

**User Story:** As a new contributor, I want the platform documentation audited for accuracy and
completeness, so that the repository's stated state matches reality.

#### Acceptance Criteria

1. THE Review_Process SHALL audit the repository documentation against the current platform state
   and record each inaccuracy in the Remediation_Plan.
2. WHEN a documented deployment path cannot be executed, THE Review_Process SHALL record a
   Remediation_Plan entry that states the executable status of that path.
3. WHERE documentation tasks T-103, T-304, or T-401 remain open, THE Review_Process SHALL record a
   Remediation_Plan entry for each open task.
4. IF documentation publication depends on GitHub Wiki write access, THEN THE Review_Process SHALL
   record an Escalation_Record referencing `REVIEW.md` R-009.

### Requirement 10: Human-gated blocker boundary

**User Story:** As a project lead, I want automated remediation to stop cleanly at human-gated
blockers, so that no automated change attempts an action that requires external ownership.

#### Acceptance Criteria

1. THE Review_Process SHALL treat every open `REVIEW.md` blocker as out of scope for automated
   remediation.
2. WHEN a remediation would require a live cloud deploy, secret provisioning, or account setup,
   THE Review_Process SHALL stop the remediation and record an Escalation_Record.
3. WHERE a `REVIEW.md` blocker's status is closed, THE Review_Process SHALL treat its subject as
   in scope for automated remediation, and WHERE a `REVIEW.md` blocker's status is not closed, THE
   Review_Process SHALL treat its subject as out of scope even when the blocker is labeled
   resolved.
4. IF a Remediation_Plan entry is an Escalation_Record, THEN THE Review_Process SHALL record the
   owning `REVIEW.md` blocker identifier for that entry.
