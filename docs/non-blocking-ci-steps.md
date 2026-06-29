# Non-Blocking CI Steps Registry

`continue-on-error: true` makes a step (or job) report failure **without failing the
workflow**. It is a deliberate exemption from "green means everything passed," so each use
must be **justified, tracked, and re-evaluated** — otherwise exemptions accumulate and a
green check stops meaning anything.

**This file is the single source of truth for every non-blocking step in CI.** Adding
`continue-on-error` without a row here should fail review.

## Policy (best practices)

1. **Default is blocking.** A step is non-blocking only for one of the accepted reasons
   below. "It's flaky" is not a reason — fix the flake or quarantine it explicitly.
2. **Every `continue-on-error` carries an inline comment** stating *why* and linking the
   tracking issue (if it's a temporary unblock).
3. **Two categories, treated differently:**
   - **Permanent / by-design** — the step is advisory by nature (e.g. a scanner that
     needs a license we don't have, best-effort cleanup, optional drift preview). These
     stay, but are listed here so reviewers know they're intentional.
   - **Temporary unblock** — masking a real bug to keep the pipeline moving. These **must**
     have an open issue and a removal trigger. They are debt, not design.
4. **Temporary unblocks must surface, not hide.** Prefer emitting a `::warning::` (or a
   step-summary note) when a non-blocking step fails, so it's visible in the run rather
   than silently swallowed.
5. **Re-evaluate on a cadence.** Temporary entries are reviewed when their issue closes;
   if an issue stalls, the entry is escalated, not forgotten.
6. **Scope to the step, not the job, where possible.** Job-level `continue-on-error` masks
   *every* step in the job. Use it only when the whole job is genuinely advisory.

## Registry

| # | Workflow | Step / Job | Scope | Category | Reason | Tracking |
|---|---|---|---|---|---|---|
| 1 | `300-test-codebase.yml` | `secret-scan` job / "Run gitleaks" | job + step | **Permanent** | gitleaks requires a paid license on private repos; runs best-effort | by-design |
| 2 | `330-teardown.yml` | `cleanup-drift` job ("Remove drifted resources") | job | **Permanent** | Best-effort cleanup of resources not in TF state; nothing to clean / pwsh-absent must not fail teardown | by-design |
| 3 | `211-deploy-azure-split.yml` | "Terraform plan (workload)" (pre-platform artifact plan) | step | **Permanent** | Greenfield deploys legitimately fail here (platform doesn't exist yet); the apply job re-plans workload afterward | by-design |
| 4 | `211-deploy-azure-split.yml` | "Validate Foundry private DNS and managed identity inference" | step | **Temporary** | Post-deploy smoke test; infra has already applied. Masks the UAI token path + the in-flux inference target | #98, #99 |
| 5 | `211-deploy-azure-split.yml` | "Query Application Insights telemetry directly" | step | **Temporary** | Verify-phase step querying App Insights, which was removed. Now effectively a no-op; the step should be removed, not just skipped | #100 |
| 6 | `211-deploy-azure-split.yml` | "Sync Entra app web URLs" | step | **Temporary** | Deploy SP lacks Microsoft Graph permission to update the Entra app redirect URI; non-blocking until the sync moves to bootstrap or the SP is granted Graph rights | #101 |

## Removal triggers (temporary entries)

- **#4 (Foundry validation):** remove `continue-on-error` once #99 (UAI token) is fixed
  **and** #98 repoints the validation to Azure OpenAI (or the step is dropped). A passing,
  meaningful validation should block again.
- **#5 (App Insights query):** delete the step entirely as part of #100 (Anthropic + dead
  observability cleanup). It queries a resource that no longer exists.
- **#6 (Entra URL sync):** remove `continue-on-error` once #101 is resolved — either by
  moving the redirect-URI sync into `Initialize-CnaGitHubSecrets.ps1` (which runs as a
  Graph-capable user) or granting the deploy SP `Application.ReadWrite.OwnedBy` + ownership
  of the NextAuth app. The sync should block again once it can actually succeed.

## What "green" currently means

With entries #4–#6 non-blocking, a green `211` run guarantees the **infrastructure applied
and the app deployed**, but does **not** yet guarantee: Foundry/OpenAI inference reachable
via managed identity (#99), nor that the Entra redirect URI is synced (#101). Those are
verified out-of-band until the temporary entries are removed. Keep this paragraph honest as
entries change.

---

_Maintained alongside CI changes. Last updated 2026-06-29._
