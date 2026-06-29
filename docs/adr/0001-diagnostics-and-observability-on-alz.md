# ADR 0001: Diagnostics and Observability Ownership on a Governed ALZ

- **Status:** Accepted
- **Date:** 2026-06-29
- **Deciders:** Platform/DevOps (CNA)
- **Related:** [alz-deployment-runbook.md](../alz-deployment-runbook.md),
  [blog: deploying into a governed ALZ](../blog/deploying-into-a-governed-azure-landing-zone.md)

## Context

CNA deploys onto **governed Azure Landing Zone (ALZ)** subscriptions (current: the
`cbtssandbox` MG hierarchy; future: client ALZs). These subscriptions are controlled by
management-group-scoped policy that the CNA deploy identity does not own.

Two observability-related facts drove this decision, both discovered during the first
end-to-end dev deploy (2026-06-29):

1. **An ALZ DeployIfNotExists (DINE) policy auto-creates diagnostic settings**
   (`setByPolicy-*`) on every supported resource the moment it is created, shipping logs
   to a centrally-governed Log Analytics workspace. Our Terraform also created its own
   per-resource `azurerm_monitor_diagnostic_setting`. The two collided: during the
   firewall's ~10-minute provisioning, the provider's create-time existence check fired
   inside the policy's remediation window and returned a false
   *"already exists / needs to be imported into State."* A `time_sleep` "stabilization
   delay" could not reliably avoid this for slow resources.

2. **We attempted to detect the ALZ policy and adapt.** A pre-flight script walked the
   subscription's management-group ancestors to find the diagnostics policy and set
   `manage_diagnostic_settings` accordingly. It ran as the **deploy service principal**,
   which **cannot read management groups**, so it always scanned a single scope, found
   nothing, and **failed open** to "Terraform manages diagnostics" — re-triggering the
   collision.

Separately, **Application Insights** was provisioned by the AI module and wired into every
container, but the application code never consumed it (no SDK usage, no env-var reads).
Its Key Vault secret was also **denied** by the ALZ guardrail *"Secrets should have the
specified maximum validity period"* (`Enforce-GR-KeyVault`), failing the deploy with
`403 ForbiddenByGovernancePolicy`.

## Decision

**1. Terraform does not manage per-resource diagnostic settings on CNA deployments.**

- `manage_diagnostic_settings` defaults to `false` in the dev/prod platform environments
  and the `observability` module.
- The ALZ DINE policy owns diagnostics; logs flow to the central governed workspace.
- The deploy workflow **does not** wire `manage_diagnostic_settings` to any runtime
  detection. The safe static default governs. (Managing diagnostics on a *non-governed*
  subscription is opt-in via `TF_VAR_manage_diagnostic_settings=true`.)

**2. We do not rely on deploy-time detection of management-group governance.**

- Logic that adapts to the environment must run as an identity that can read that
  environment. The deploy SP cannot read MG-scoped policy, so detection-driven decisions
  are forbidden where a safe static default exists.

**3. Application Insights is removed entirely (dev + prod).**

- The `azurerm_application_insights` resource, its KV secret, container env-var wiring,
  observability diagnostic target, GitHub variables, module outputs, and the App
  Insights telemetry FQDNs in the firewall egress allowlist are all deleted.
- Application telemetry, if reintroduced, will be a deliberate decision with real code
  consumers — not provisioned-but-unused infrastructure.

## Consequences

### Positive

- The diagnostic-setting create-race is structurally impossible — Terraform creates none.
- No dependency on RBAC (MG read) that the deploy SP lacks; nothing can "fail open."
- One ALZ governance deny (the App Insights secret validity violation) is eliminated, and
  ~185 lines of dead observability config are gone.
- Behavior is identical and predictable across any ALZ subscription, regardless of which
  diagnostics policy is assigned.

### Negative / trade-offs

- **CNA-managed diagnostics are off by default**, including on non-ALZ subscriptions. If
  CNA is ever deployed to an ungoverned subscription that needs per-resource diagnostics,
  the operator must explicitly set `TF_VAR_manage_diagnostic_settings=true`. This is
  documented and intentional (fail safe, not fail managed).
- **No application telemetry** until/unless App Insights (or an alternative) is
  reintroduced with real consumers. Acceptable now because nothing used it.
- Diagnostic logs live only in the **org's central workspace**, not a CNA-local one.
  Querying them requires access to that workspace. Acceptable on an ALZ where central
  observability is the org's model.

### Latent risk (tracked, not resolved here)

- The ALZ *"maximum validity period"* secret guardrail still governs the **remaining** KV
  secrets' 90-day expiry. App Insights tripped it first only because it lacked the
  `ignore_changes = [expiration_date]` lifecycle the others have. If a future fresh secret
  create is denied, set `secret_expiration_date` within the policy's allowed window. The
  exact limit is in the `Enforce-GR-KeyVault` assignment at the `cbtssandbox-landing-zones`
  MG (not readable by the deploy SP).

## Alternatives considered

- **Dual-ship (keep managing our own uniquely-named diagnostic settings alongside the
  policy's).** Rejected: this was the original design and is what caused the create-race;
  Azure allows multiple settings per resource but the provider's create-time existence
  check races the policy's remediation. No stabilization delay reliably avoids it.
- **Fix the detection to read management groups (grant the deploy SP MG Reader).**
  Rejected: expands the deploy identity's privilege for a decision that has a safe static
  default, and still leaves a fail-open path if the grant is ever missing on a client
  tenant.
- **Keep App Insights, set its secret expiry within the policy window.** Rejected: the
  resource was unused; complying with the guardrail would have preserved dead infra.

## Implementation

Commits (2026-06-29): `b05efea`, `fcb13ec` (diagnostics stand-down), `4ea071a` (App
Insights removal). Verified by `terraform validate` (dev/prod workload, dev platform),
`terraform fmt`, and a clean grep for `application_insights` across `infra/terraform`.
