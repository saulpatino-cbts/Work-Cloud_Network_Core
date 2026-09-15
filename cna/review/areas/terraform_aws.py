"""Findings for the ``terraform-aws`` area (Requirement 4 AWS hardening).

This is a *verify-then-close-gaps* record for the authored-but-never-applied AWS
Terraform under ``infra/terraform/providers/aws/`` (the eight module boundaries
``ai, compute, database, identity, observability, runtime, security, storage``)
and the ``dev``/``prod`` ``platform`` + ``workload`` roots under
``infra/terraform/environments/aws/``. The audit against Requirement 4.1 covers
tagging, encryption defaults, least-privilege IAM shapes, security-group
tightening, S3 versioning/SSE, and edge/WAF/CloudFront posture.

Because the AWS path has no account (``REVIEW.md`` R-001) and no state backend
(R-002), this audit applies *every* correction engineering allows without an
account and records the rest as findings. The ``blocker_id`` mapping for the
gated findings (R-001–R-006) is deliberately **not** set here — spec task 7.2
owns that mapping and the ``terraform validate`` gate, exactly as ``cicd.py``
leaves the R-003 escalation to spec task 9.3 so the two tasks do not
double-count. Findings whose remediation needs account access, a state backend,
an OIDC deploy role, an ACM certificate, Bedrock access, or a runtime secret
carry a ``gated:<kind>`` marker in their ``dedup_key`` so task 7.2 can map each
to the matching blocker.

Best-practice fixes applied in-tree by this task (account-independent, no live
resource required):

  * **storage/main.tf — static-site bucket.** Added an explicit
    ``aws_s3_bucket_server_side_encryption_configuration`` (AES256/SSE-S3, not
    SSE-KMS — SSE-KMS is deliberately avoided so CloudFront OAC reads need no
    ``kms:Decrypt``) and ``aws_s3_bucket_versioning`` (Enabled). The artifacts
    bucket already had SSE-KMS + versioning + public-access-block; the static
    bucket had only the public-access-block, so encryption-at-rest was implicit
    and versioning absent.
  * **observability/main.tf — alarms SNS topic.** Set ``kms_master_key_id`` so
    the topic is encrypted at rest with the customer-managed key when supplied
    and the AWS-managed ``alias/aws/sns`` key otherwise — the topic was
    previously unencrypted.
  * **compute/main.tf — ALB.** Set ``drop_invalid_header_fields = true`` so the
    load balancer strips malformed headers instead of forwarding them to the
    tasks (request-smuggling / header-injection defense).

``terraform fmt``/``validate`` verification and the gated→R-001..R-006 mapping
are recorded by spec task 7.2. These records are consumed by the consolidation
step (spec task 14.1).
"""

from __future__ import annotations

from cna.review.model import Finding, Severity

_AREA = "terraform-aws"

# The eight AWS module boundaries, kept in sync with
# infra/terraform/providers/aws/. Coverage of all eight is asserted by the area
# test and by the consolidation coverage check (spec task 14.2, Property 2).
AWS_MODULES: tuple[str, ...] = (
    "ai",
    "compute",
    "database",
    "identity",
    "observability",
    "runtime",
    "security",
    "storage",
)


def _module_subject(module: str) -> str:
    """Return the repo-relative subject path for an AWS provider module."""
    return f"infra/terraform/providers/aws/{module}"


def _verified_finding(module: str, action: str) -> Finding:
    """Record a per-module verified-compliant outcome as INFORMATIONAL.

    Recorded so the consolidated plan reflects that every one of the eight
    module boundaries was audited (design Property 2), not only the ones with a
    residual gap.
    """
    return Finding(
        area=_AREA,
        severity=Severity.INFORMATIONAL,
        proposed_action=action,
        dedup_key=f"terraform-aws:module-audited:{module}",
        subject=_module_subject(module),
    )


def _applied_fixes() -> list[Finding]:
    """Account-independent best-practice corrections applied in-tree by 7.1."""
    return [
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "Static-site S3 bucket declared encryption-at-rest only "
                "implicitly and had no versioning. Added an explicit "
                "aws_s3_bucket_server_side_encryption_configuration (AES256 / "
                "SSE-S3 — not SSE-KMS, so CloudFront OAC reads need no "
                "kms:Decrypt) and aws_s3_bucket_versioning (Enabled). Applied by "
                "this task."
            ),
            dedup_key="terraform-aws:s3-static-sse-versioning",
            subject="infra/terraform/providers/aws/storage/main.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "Alarms SNS topic was created without encryption at rest. Set "
                "kms_master_key_id to the customer-managed key when supplied and "
                "alias/aws/sns otherwise, so alarm notifications are never stored "
                "unencrypted. Applied by this task."
            ),
            dedup_key="terraform-aws:sns-topic-encryption",
            subject="infra/terraform/providers/aws/observability/main.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "Application Load Balancer did not drop invalid HTTP header "
                "fields, so malformed headers were forwarded to the tasks. Set "
                "drop_invalid_header_fields = true (request-smuggling / "
                "header-injection defense). Applied by this task."
            ),
            dedup_key="terraform-aws:alb-drop-invalid-headers",
            subject="infra/terraform/providers/aws/compute/main.tf",
        ),
    ]


def _residual_fixable_findings() -> list[Finding]:
    """Best-practice gaps that are account-independent but not auto-applied.

    These carry a concrete remediation but were not applied in-tree because the
    correct value depends on an operator choice (a log-destination bucket, a
    pinned image tag, a cost/latency trade-off) rather than a live account
    credential — so they are fixable plan entries, not escalations.
    """
    return [
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "CloudFront distribution has no access logging (logging_config) "
                "and the WAF web ACL has no logging configuration "
                "(aws_wafv2_web_acl_logging_configuration). Add both, pointing at "
                "an operator-chosen log destination (an S3 log bucket for "
                "CloudFront; a CloudWatch log group or Firehose for WAF), so edge "
                "traffic and blocked requests are auditable. Not auto-applied: the "
                "log destination is an operator choice, not account-gated."
            ),
            dedup_key="terraform-aws:edge-access-logging",
            subject="infra/terraform/providers/aws/security/main.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "The X-Ray daemon sidecar pins its image to a mutable "
                "'aws-xray-daemon:latest' tag, so a rebuild can silently change "
                "the running daemon version. Pin to a specific published tag (or "
                "an image digest) for reproducible task definitions. Not "
                "auto-applied: the specific pinned version is an operator choice."
            ),
            dedup_key="terraform-aws:xray-sidecar-latest-tag",
            subject="infra/terraform/providers/aws/compute/locals.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "RDS instance enables neither Performance Insights "
                "(performance_insights_enabled) nor enhanced monitoring "
                "(monitoring_interval + a monitoring role) nor IAM database "
                "authentication (iam_database_authentication_enabled). Consider "
                "enabling these for production observability and credential-free "
                "auth. Not auto-applied: each carries a cost/behavior trade-off "
                "and enhanced monitoring needs a monitoring IAM role."
            ),
            dedup_key="terraform-aws:rds-observability-options",
            subject="infra/terraform/providers/aws/database/main.tf",
        ),
    ]


def _gated_findings() -> list[Finding]:
    """Findings whose remediation crosses a human-gated REVIEW.md boundary.

    Recorded here as plain findings (no ``blocker_id`` — spec task 7.2 owns the
    R-001..R-006 mapping and the ``terraform validate`` gate, mirroring how the
    CI/CD area leaves its R-003 escalation to spec task 9.3). The ``gated:<kind>``
    marker in each ``dedup_key`` names the dependency kind so task 7.2 can map it
    to the matching blocker:

      * ``gated:account``       → R-001 (AWS account / admin access)
      * ``gated:state-backend`` → R-002 (S3 state backend + DynamoDB lock)
      * ``gated:oidc-role``     → R-003 (GitHub OIDC deploy role)
      * ``gated:certificate``   → R-004 (ACM certs + custom-domain decision)
      * ``gated:bedrock``       → R-005 (Bedrock model access opt-in)
      * ``gated:runtime-secret``→ R-006 (runtime secrets supplied at deploy)
    """
    return [
        Finding(
            area=_AREA,
            severity=Severity.HIGH,
            proposed_action=(
                "The whole AWS stack is authored but never applied: no account is "
                "available (REVIEW.md R-001), so terraform plan/apply against a "
                "real account and any account-scoped validation cannot run. "
                "Escalate — do not attempt a live apply (Requirement 4.6)."
            ),
            dedup_key="terraform-aws:gated:account",
            subject="infra/terraform/environments/aws",
        ),
        Finding(
            area=_AREA,
            severity=Severity.HIGH,
            proposed_action=(
                'Both env roots declare an empty S3 backend (backend "s3" {}) '
                "populated via -backend-config at init. No S3 state bucket or "
                "DynamoDB lock table exists yet (REVIEW.md R-002), so "
                "'terraform init' with a backend cannot run and validate must use "
                "-backend=false. Escalate provisioning of the state backend."
            ),
            dedup_key="terraform-aws:gated:state-backend",
            subject="infra/terraform/environments/aws/dev/platform/providers.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.HIGH,
            proposed_action=(
                "The identity module creates the GitHub OIDC deploy role and a "
                "broad deploy-write policy (ec2:*, rds:*, s3:*, iam:*, kms:* on "
                "Resource '*'; ECS is Project-tag scoped). Tightening the "
                "wildcard actions to concrete resource ARNs, and wiring CI to the "
                "role, both require the live account and the externally "
                "provisioned OIDC role (REVIEW.md R-003) — the real resource ARNs "
                "are not known without an account. Escalate; record the "
                "least-privilege tightening as a follow-up once the account "
                "exists."
            ),
            dedup_key="terraform-aws:gated:oidc-role",
            subject="infra/terraform/providers/aws/identity/main.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "HTTPS on the ALB (aws_lb_listener.https) and the custom-domain "
                "CloudFront alias are gated on an ACM certificate ARN that is "
                "created and validated externally (REVIEW.md R-004). Without a "
                "cert the HTTPS listener and the API path rule are count=0 and the "
                "distribution uses the default CloudFront certificate. Escalate "
                "the certificate + custom-domain decision."
            ),
            dedup_key="terraform-aws:gated:certificate",
            subject="infra/terraform/providers/aws/compute/main.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "The ai module authors the Bedrock invoke policy, inference "
                "profile, and (optional) provisioned throughput, but Bedrock "
                "foundation-model access must be enabled manually in the Bedrock "
                "console per region/account before any invocation succeeds "
                "(REVIEW.md R-005) — there is no Terraform resource for the "
                "opt-in. Escalate the model-access opt-in."
            ),
            dedup_key="terraform-aws:gated:bedrock",
            subject="infra/terraform/providers/aws/ai/main.tf",
        ),
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "The runtime module writes Secrets Manager secrets (DATABASE_URL, "
                "nextauth, Entra client secret, credential-encryption key, "
                "optional Docker Hub creds) whose values are supplied at deploy "
                "time by an external owner (REVIEW.md R-006). secret_string is "
                "ignored after creation. Escalate provisioning of the real secret "
                "values — never invent or commit one."
            ),
            dedup_key="terraform-aws:gated:runtime-secret",
            subject="infra/terraform/providers/aws/runtime/main.tf",
        ),
    ]


def terraform_aws_findings() -> list[Finding]:
    """Return the Requirement 4.1 findings recorded for the AWS Terraform area.

    Combines: a per-module verified-compliant record for each of the eight
    module boundaries, the account-independent best-practice fixes this task
    applied in-tree, the residual fixable best-practice gaps left for an operator
    choice, and the human-gated dependencies (recorded as plain findings for spec
    task 7.2 to map to R-001..R-006).
    """
    verified = [
        _verified_finding(
            "ai",
            "Verified compliant: Bedrock invoke policy is scoped to the "
            "configured foundation-model / inference-profile ARNs (no bedrock:* "
            "wildcard), guardrail + inference profile are optional and tagged.",
        ),
        _verified_finding(
            "compute",
            "Verified compliant: ECS Fargate tasks run in private subnets "
            "(assign_public_ip=false), have healthchecks, awslogs logging, "
            "container-insights on, autoscaling with scale-to-zero, and the ALB "
            "redirects HTTP→HTTPS. ALB drop_invalid_header_fields added by 7.1.",
        ),
        _verified_finding(
            "database",
            "Verified compliant: RDS is not publicly accessible, storage is "
            "KMS-encrypted, backups + final-snapshot + deletion-protection are "
            "environment-driven, postgresql logs export to CloudWatch, password "
            "is sensitive and ignored after create.",
        ),
        _verified_finding(
            "identity",
            "Verified compliant: KMS key rotation on; ECS execution/task roles "
            "are name-prefix-scoped to their secrets/buckets/KMS; OIDC subject is "
            "pinned to the repo. Broad deploy-write policy is recorded as a "
            "gated (R-003) tightening follow-up.",
        ),
        _verified_finding(
            "observability",
            "Verified compliant: CloudWatch log groups are KMS-encrypted with "
            "retention; X-Ray sampling, metric filters, and baseline alarms are "
            "present. Alarms SNS topic encryption added by 7.1.",
        ),
        _verified_finding(
            "runtime",
            "Verified compliant: Secrets Manager secrets are namespaced, "
            "recovery-window is environment-driven, and secret_string is ignored "
            "after create so external rotation does not drift. Real values are a "
            "gated (R-006) deploy-time input.",
        ),
        _verified_finding(
            "security",
            "Verified compliant: WAFv2 (CLOUDFRONT scope, us-east-1) with AWS "
            "managed rule groups + Auth.js field-scoped exclusions; CloudFront "
            "OAC + origin protocol https-only + viewer redirect-to-https; "
            "static-site bucket policy scoped to the distribution ARN. Access "
            "logging recorded as a fixable follow-up.",
        ),
        _verified_finding(
            "storage",
            "Verified compliant: artifacts bucket has SSE-KMS, versioning, "
            "public-access-block, and lifecycle tiering. Static-site bucket SSE "
            "(AES256) + versioning added by 7.1.",
        ),
    ]
    return verified + _applied_fixes() + _residual_fixable_findings() + _gated_findings()
