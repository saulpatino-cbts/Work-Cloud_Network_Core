# Review — human-resolvable blockers

This file tracks **only** items that an engineer cannot resolve independently. Every entry
requires external input: an approval, a credential, an account, an access grant, or a decision
that belongs to a named owner outside the engineering task itself.

Anything an engineer can solve without external input belongs in [`TODO.md`](TODO.md), not here.

**Last reviewed:** 2026-08-28

| ID | Blocker | Owner | Status |
|---|---|---|---|
| [R-001](#r-001--aws-account-and-administrative-access) | AWS account + administrative access for first deploy | AWS account owner | Open |
| [R-002](#r-002--terraform-s3-state-backend-must-be-created-out-of-band) | Terraform S3 state backend + DynamoDB lock table | AWS account owner | Open |
| [R-003](#r-003--github-oidc-deploy-role-must-be-wired-into-ci) | GitHub OIDC deploy role wired into CI secrets | Repository admin | Open |
| [R-004](#r-004--acm-certificates-and-custom-domain-decision) | ACM certificates + custom-domain decision | DNS / domain owner | Open |
| [R-005](#r-005--amazon-bedrock-model-access-opt-in) | Amazon Bedrock foundation-model access opt-in | AWS account owner | Open |
| [R-006](#r-006--runtime-secrets-have-no-defaults-and-must-be-supplied) | Runtime secrets supplied at apply time | Security / secret owner | Open |
| [R-007](#r-007--azure-subscription-resource-provider-registration) | `Microsoft.AlertsManagement` provider registration | Azure subscription owner | Resolved — no longer required |
| [R-008](#r-008--live-azure-beta-acceptance-sign-off) | 0.8 beta exit — live Azure acceptance sign-off | Product owner | Open — deploy done 2026-08-28, acceptance outstanding |
| [R-009](#r-009--github-wiki-write-access-for-documentation-migration) | GitHub Wiki write access to publish prepared pages | Repository owner | Open — not blocking |
| [R-010](#r-010--the-dev-environment-has-no-protection-against-out-of-band-deletion) | Dev environment deleted out of band; no protection against a repeat | Azure subscription owner | Open |

---

## R-001 — AWS account and administrative access

**Problem**
The AWS Terraform under `infra/terraform/providers/aws/` and
`infra/terraform/environments/aws/` declares real resources across all eight module boundaries
(90 resources total), but none of it has ever been applied. There is no AWS account, no
administrative principal, and no bootstrap identity available to the engineering team.

**Why it blocks progress**
No AWS deployment step can begin. `terraform init` cannot reach a backend, `terraform plan`
cannot authenticate, and workflow `212-deploy-aws-split.yml` cannot be made functional. This is
the root dependency for R-002 through R-006.

**Required owner**
AWS account owner / cloud finance approver (account creation carries a billing commitment).

**Required action**
1. Provision or nominate the AWS account(s) for `dev` and `prod`.
2. Confirm the deployment region (the Terraform takes it as `var.aws_region`; a fixed
   `us-east-1` aliased provider is used for the CloudFront-scoped WAF regardless).
3. Grant an engineer a principal able to create IAM roles, an OIDC provider, S3, DynamoDB,
   VPC, ECS, RDS, CloudFront, WAFv2, KMS, Secrets Manager, and CloudWatch resources.

**Impact if unresolved**
AWS parity work stays code-only indefinitely. The repository continues to advertise an AWS
deployment path that cannot be executed, and the AWS half of the platform cannot be validated
before a customer engagement.

**References**
- `infra/terraform/providers/aws/` (ai, compute, database, identity, observability, runtime,
  security, storage)
- `infra/terraform/environments/aws/{dev,prod}/{platform,workload}/`
- `.github/workflows/212-deploy-aws-split.yml`
- Tracking issue [#110](https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110)

**Recommended next step**
Name the account owner and confirm the target region and environment count (dev-only first, or
dev + prod together) before any further AWS engineering effort is scheduled.

---

## R-002 — Terraform S3 state backend must be created out of band

**Problem**
Every AWS root uses an empty `backend "s3" {}` block — the same init-time-configuration pattern
the Azure side uses for `backend "azurerm" {}`. The bucket and lock table must exist before the
first `terraform init`, and Terraform cannot create the backend it is about to use.

**Why it blocks progress**
`terraform init` fails without `-backend-config` values pointing at a real bucket and table. The
platform state and the workload state are separate, so both keys must be agreed before the first
plan.

**Required owner**
AWS account owner (depends on R-001).

**Required action**
Create, out of band or via a one-time bootstrap job mirroring Azure's
`000-bootstrap-backend.yml`:

| Input | What it is | How it is supplied |
|---|---|---|
| State bucket | S3 bucket for Terraform state, versioning + SSE enabled | `terraform init -backend-config="bucket=..."` |
| Lock table | DynamoDB table with a `LockID` (S) partition key | `-backend-config="dynamodb_table=..."` |
| State key | State object path | `-backend-config="key=aws/<env>/<platform\|workload>.tfstate"` |
| Region | Backend region | `-backend-config="region=..."` |

**Impact if unresolved**
No AWS Terraform command past `validate` can run. State would otherwise be local and
unshareable, which is unsafe for a CI-driven deploy.

**References**
- `infra/terraform/environments/aws/{dev,prod}/{platform,workload}/providers.tf`
- `.github/workflows/000-bootstrap-backend.yml` (the Azure equivalent to mirror)

**Recommended next step**
Decide bucket and table naming (the Azure convention is
`rg-cna-<env>-<region_short>-tfstate`; mirror it for AWS), then create them and record the four
`-backend-config` values in the repository's Actions variables.

---

## R-003 — GitHub OIDC deploy role must be wired into CI

**Problem**
The `identity` module provisions the GitHub OIDC provider and a deploy role assumable via
`AssumeRoleWithWebIdentity`, and exports it as the `github_deploy_role_arn` output. Nothing
consumes that output. CI trigger configuration was deliberately left out of scope of the AWS
code-generation work.

**Why it blocks progress**
Workflow `212-deploy-aws-split.yml` has no credential to assume, so it cannot authenticate to AWS
even once the guards are removed. The role ARN is account-specific and cannot be committed.

**Required owner**
Repository admin (GitHub secrets/variables) together with the AWS account owner (role creation).

**Required action**
1. Supply `github_owner` and `github_repository` as real values — they currently default to
   `<GITHUB_OWNER_PLACEHOLDER>` / `<GITHUB_REPO_PLACEHOLDER>` in
   `infra/terraform/providers/aws/identity/variables.tf` and
   `infra/terraform/environments/aws/{dev,prod}/workload/variables.tf`.
2. Apply the `identity` module, or import an existing OIDC provider if the account already has
   one (AWS permits only one GitHub OIDC provider per account).
3. Store the resulting `github_deploy_role_arn` as a repository secret and reference it from
   workflow 212.

**Impact if unresolved**
AWS CI/CD stays non-functional. Any interim workaround would mean long-lived AWS access keys in
GitHub, which contradicts the repository's OIDC-only credential policy.

**References**
- `infra/terraform/providers/aws/identity/` (`aws_iam_openid_connect_provider.github`)
- `.github/workflows/212-deploy-aws-split.yml`
- Related engineering task: [`TODO.md`](TODO.md) → T-201, T-202

**Recommended next step**
Confirm whether the target account already has a GitHub OIDC provider. If it does, the module
must import it rather than create it — plan for that before the first apply.

---

## R-004 — ACM certificates and custom-domain decision

**Problem**
TLS certificates are taken as **inputs** (`alb_certificate_arn`, `acm_certificate_arn`, both
defaulting to `null`). The Terraform deliberately does not mint an `aws_acm_certificate`, because
an unvalidated certificate resource hangs waiting on DNS validation.

**Why it blocks progress**
Without certificate ARNs the ALB HTTPS listener and the CloudFront viewer certificate cannot be
configured. The CloudFront certificate additionally **must** live in `us-east-1` regardless of
the deployment region.

**Required owner**
DNS / domain owner (certificate request and DNS validation records), with product input on
whether a custom domain is in scope for beta.

**Required action**
1. Decide whether the beta uses a custom domain (`custom_domain_name`, default `""`) or the
   generated CloudFront domain.
2. If a custom domain is used: request the two ACM certificates (regional for the ALB,
   `us-east-1` for CloudFront), publish the DNS validation records, and pass both ARNs in.
3. If Route 53 hosts the zone, an `aws_acm_certificate_validation` flow can be added instead —
   that is an engineering task once the zone owner is confirmed (see `TODO.md` → T-502).

**Impact if unresolved**
The AWS stack can only be deployed without HTTPS termination at the edge, which is not
acceptable for a client-facing delivery portal.

**References**
- `infra/terraform/providers/aws/compute/` (ALB listener), `infra/terraform/providers/aws/security/`
  (CloudFront + WAFv2)

**Recommended next step**
Confirm the domain decision first — it determines whether R-004 is a two-certificate task or a
single CloudFront-default deployment with no certificate work at all.

---

## R-005 — Amazon Bedrock model access opt-in

**Problem**
Amazon Bedrock foundation-model access is granted per account **and** per region through a
console opt-in. No Terraform resource covers this step.

**Why it blocks progress**
`bedrock:InvokeModel` fails until the opt-in is complete, so the `ai` module's inference profile
resolves to a model the platform cannot call. The AI analysis path is a core platform capability,
not an optional extra.

**Required owner**
AWS account owner (the opt-in requires console access and acceptance of model EULA terms).

**Required action**
1. Enable foundation-model access in the Bedrock console for the deployment account and region.
2. Confirm the model IDs in the `ai` module's `model_ids` variable are available in that region;
   adjust the variable if not (that adjustment is an engineering task — `TODO.md` → T-303).

**Impact if unresolved**
AWS AI analysis is unavailable. The fallback is to keep calling the existing Azure OpenAI
endpoint from the AWS deployment, which reintroduces a cross-cloud dependency the AWS parity work
was meant to remove.

**References**
- `infra/terraform/providers/aws/ai/`
- Azure equivalent: AI Foundry `cognitive_deployment`, already Terraform-managed

**Recommended next step**
Perform the opt-in at the same time as R-001 account setup — it is a prerequisite with a
multi-hour approval delay for some models, so it should not be discovered late.

---

## R-006 — Runtime secrets have no defaults and must be supplied

**Problem**
Five runtime inputs are declared `sensitive` with **no defaults** and are intentionally absent
from the repository.

**Why it blocks progress**
`terraform apply` on the workload root fails immediately without them. They cannot be committed,
generated by CI, or defaulted safely.

**Required owner**
Security / secret owner (whoever holds the Entra app registration and the Docker Hub
organization).

**Required action**
Supply at apply time, or seed into the chosen secret store:

| Variable | Purpose |
|---|---|
| `db_admin_password` | RDS PostgreSQL master password |
| `nextauth_secret` | NextAuth / Auth.js session secret |
| `entra_client_secret` | Entra ID app-registration client secret |
| `credential_encryption_key` | Application credential-encryption key |
| `dockerhub_username` / `dockerhub_token` | Private image pulls (optional — the module counts off when blank) |

**Impact if unresolved**
No workload apply is possible. Partial supply is worse than none: the database and runtime
modules would apply inconsistently and leave a half-provisioned environment.

**References**
- `infra/terraform/providers/aws/runtime/variables.tf`,
  `infra/terraform/providers/aws/database/variables.tf`
- `.env.example` (the equivalent Azure secret inventory)

**Recommended next step**
Decide where these live for AWS — Secrets Manager seeded out of band, or GitHub environment
secrets passed as `TF_VAR_*`. The Azure side uses Key Vault; the AWS `runtime` module already
provisions Secrets Manager entries, so seeding is the closer mirror.

---

## R-007 — Azure subscription resource-provider registration

**Status: Resolved — nothing is required of the subscription owner.**

**Original problem**
The Azure subscription was said to need `Microsoft.AlertsManagement` registered before workflow
`211-deploy-azure-split.yml` runs, because Application Insights smart-detection alert deployment
fails during apply if it is not, ~20 minutes into a run.

**Why it is no longer required**
The split refactor removed alerting from the Azure roots entirely. Verified against the current
Terraform on 2026-08-18 (`TODO.md` → T-104): `infra/` contains no `azurerm_application_insights`,
no `azurerm_monitor_smart_detector_alert_rule`, no `azurerm_monitor_metric_alert`, and no
`azurerm_monitor_action_group`. The only monitor resource left is
`azurerm_monitor_diagnostic_setting`, which belongs to `Microsoft.Insights`, not
`Microsoft.AlertsManagement`. Both `azapi_resource` declarations resolve to
`Microsoft.CognitiveServices` and `Microsoft.Network`. Workflow `100-validate-prereqs.yml` had
already reached the same conclusion in a code comment; this is the check against the Terraform
that confirms it.

**What replaced it**
Provider registration is now *asserted*, not assumed. Workflow `100-validate-prereqs.yml` checks
all ten namespaces the roots genuinely need — `Microsoft.App`, `.Network`, `.Storage`, `.KeyVault`,
`.DBforPostgreSQL`, `.CognitiveServices`, `.OperationalInsights`, `.Insights`, `.Cdn`, and
`.ManagedIdentity` — and fails in seconds with the exact `az provider register` command rather
than partway through apply. It previously checked only two of the ten, so the *class* of blocker
R-007 describes was real and largely unguarded; it is now closed for every provider at once, not
just this one.

**2026-08-28 addendum — the leftover register call in 211**
The first full `211` run under the RG-scoped deploy identities (rebuilt dev environment) failed
in seconds on a leftover from the pre-split era: both the `plan` and `apply` jobs still ran an
unconditional `az provider register --namespace Microsoft.App --wait`, which requires the
subscription-scope `register/action` this item says the deploy identity must never hold. That
step is now a read-only verification (fails with the one-time Owner command only on
`NotRegistered`), and all four environment roots set `resource_provider_registrations = "none"`
so the azurerm provider's default auto-registration cannot hit the same wall during plan.
Workflow 100 remains the gating assertion.

**If a future change reintroduces alerting**
Add `Microsoft.AlertsManagement` to `REQUIRED_PROVIDERS` in `100-validate-prereqs.yml` in the same
commit as the alert resource, and reopen this item — the registration is still a subscription-level
operation the deploy identity cannot perform itself.

**References**
- `.github/workflows/100-validate-prereqs.yml` (the `REQUIRED_PROVIDERS` list)
- `infra/terraform/providers/azure/observability/`
- `TODO.md` → T-104

---

## R-008 — Live Azure beta acceptance sign-off

**Problem**
The repository is at `0.8.0b0`. Code, Terraform, workflows, and the changelog are aligned on
`main`, but the beta exit gate is live Azure execution: prerequisite validation, dev deploy,
Entra redirect update, runtime validation, and customer-like beta acceptance.

**Why it blocks progress**
Acceptance is a product judgement, not an engineering result. No amount of further engineering
work moves the release posture past `0.8 beta` without someone accepting the live evidence.

**Required owner**
Product owner (with the AWS/Azure account owners for the deploy windows).

**Required action**
1. ~~Schedule the live dev deploy window (workflows 100 → 200 → 211).~~ **Done 2026-08-28** —
   though not as a scheduled window: the dev environment had been deleted out of band (see R-010
   and `CNA-0.90-updates.md` §5), so it was rebuilt from nothing via `000` → `100` → `211`.
   Run `33169632082`, all jobs green.
2. **Review the deployment evidence artifacts produced by the workflow run.** These now exist:
   `.deployment-catalog/dev/33169632082.json` records `health_status: healthy`, 100% origin
   health, and passing canary, staged-promotion, certificate and private-endpoint checks.
   **Read the two `required` markers before accepting** — `foundry_private_dns_validation` and
   `foundry_managed_identity_inference` are never set by any workflow step, so a `healthy`
   verdict does not cover the AI Foundry / Copilot path (`TODO.md` → T-415).
3. Accept or reject the customer-like beta acceptance run, and record the decision.
   Note the acceptance run has not happened yet: the rebuilt environment has an empty database,
   so there is no discovery, finding, or deliverable in it to accept against.

**Impact if unresolved**
The platform stays in beta indefinitely and cannot be offered to a client engagement, regardless
of code readiness.

**References**
- `.github/workflows/100-validate-prereqs.yml`, `200-build-images.yml`,
  `211-deploy-azure-split.yml`
- `scripts/ci/evaluate_deployment_evidence.py`
- [`CHANGELOG.md`](CHANGELOG.md) → `[0.8.0-beta]`

**Recommended next step**
Book the deploy window. R-007 no longer blocks it — see that item; provider registration is now
asserted by workflow `100-validate-prereqs.yml`, which should be run first regardless.

---

## R-009 — GitHub Wiki write access for documentation migration

**Problem**
The documentation model designates the GitHub Wiki as the destination for all long-form
documentation. Seven validated pages were prepared during the consolidation and cannot be
published: the wiki remote returns HTTP 401 to the automation performing the work, while the
repository itself authenticates normally. Wiki write access is scoped out.

**Why it blocks progress**
This no longer blocks the repository — it converged on the four-document end state without the
Wiki. The long-form content that had nowhere else to go was migrated into `TODO.md` handoff notes
instead (T-304 carries the Log Analytics state-migration runbook, T-401 the `migrate/` reference),
and both source files were deleted after that migration was verified. What remains blocked is
putting that documentation in its proper home. Until then, operational runbook content lives in
the engineering backlog, which is the right fallback but the wrong destination.

**Required owner**
Repository owner.

**Required action**
Either grant Wiki write access to the account performing documentation consolidation, or publish
the seven prepared pages manually. The validated page content is attached to the pull request that
introduced this file. The corresponding tasks are `TODO.md` → T-601 (publish) and T-602 (trim the
inline copies once the Wiki has them).

**Impact if unresolved**
Low and contained. No information is lost and no competing source of truth exists — every fact is
either in the repository or in a TODO item's handoff notes. The cost is discoverability: an
operator looking for a state-migration runbook will not think to look in the engineering backlog,
and `TODO.md` carries roughly 80 lines of procedure that do not belong in a work queue.

**References**
- [`TODO.md`](TODO.md) → T-304, T-401 (the content), T-601, T-602 (the cleanup)
- [`README.md`](README.md) → documentation map, where the Wiki links belong

**Recommended next step**
Confirm the Wiki page names before publishing so the cross-links resolve — in particular
`Runbook: Log Analytics Workspace State Migration` and `Legacy AWS Migrate Root`. `Workflows
Guide` and `Secrets Reference` are already referenced by `.env.example` and may already exist;
merge rather than create.

---

## R-010 — The dev environment has no protection against out-of-band deletion

**Problem**
The entire Azure dev environment — workload resource group *and* the `-tfstate` resource group
holding the Terraform state — was deleted from `sub-cbtssandbox-ops-tst` around **2026-07-21**,
outside CI. No teardown workflow ran in that window (`330-teardown` last ran 2026-07-01), so the
deletion was performed directly against the subscription, consistent with a sandbox cost sweep.

It was rebuilt on 2026-08-28 (`CNA-0.90-updates.md` §5), but nothing prevents a repeat, and the
rebuild was not cheap: the state loss meant a from-scratch provision, six previously-unknown gaps
in the deploy identity's least-privilege role set, a soft-deleted Key Vault to recover and import,
and roughly half a day of a pre-demo schedule.

**Why it needs an owner**
Whether the sweep is intentional policy is not an engineering question. If the sandbox is *meant*
to be swept, the environment should not be treated as durable and the demo/engagement plan has to
budget a rebuild each time. If it is not meant to be swept, the environment needs protecting. Only
the subscription owner can say which.

**Required owner**
Azure subscription owner (`sub-cbtssandbox-ops-tst`), with whoever administers the sandbox
sweep policy.

**Required action**
1. Establish whether a sweep policy exists for this subscription, what it targets, and on what
   schedule.
2. If the environment should persist: apply a `CanNotDelete` resource lock to
   `rg-cna-dev-scus` and `rg-cna-dev-scus-tfstate` at minimum — the state RG especially, since
   losing it is what turned a redeploy into a rebuild — or request an exclusion from the sweep.
3. If the environment is legitimately ephemeral: record that in the demo/engagement runbook so a
   rebuild is planned rather than discovered, and consider whether the tfstate backend should live
   in a subscription that is not swept.

**Impact if unresolved**
The next sweep repeats the same half-day recovery, at whatever moment it happens to land. The
permission gaps are now codified in `scripts/Initialize-CnaGitHubSecrets.ps1`, so a second rebuild
would be materially faster — but it would still be a rebuild, with a fresh, empty database.

**References**
- [`CNA-0.90-updates.md`](CNA-0.90-updates.md) → §5 (the full rebuild record)
- [`TODO.md`](TODO.md) → T-416 (the drift check that detected this and told no one)
- `.deployment-catalog/dev/33169632082.json` (the rebuild's evidence)

**Recommended next step**
Ask the sandbox administrator the one question that decides everything else: is
`sub-cbtssandbox-ops-tst` swept on a schedule, and can these two resource groups be excluded?
