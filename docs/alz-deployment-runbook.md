# ALZ Deployment Runbook — CNA on a Governed Azure Landing Zone

Operational reference for deploying the CNA platform (workflow `211-deploy-azure-split`)
onto a **governed Azure Landing Zone (ALZ)** subscription using a **self-hosted GitHub
Actions runner**. It documents the failure modes hit during the first end-to-end dev
deploy (2026-06-29), their root causes, and the durable fixes — so the next environment
(prod, or a client ALZ) onboards without re-discovering each one.

> Companion docs: [dev-deploy-workarounds.md](dev-deploy-workarounds.md) (dev-only
> expediencies to revert for prod), [SELF_HOSTED_RUNNER_SETUP.md](SELF_HOSTED_RUNNER_SETUP.md)
> (runner provisioning), and ADR
> [0001-diagnostics-and-observability-on-alz.md](adr/0001-diagnostics-and-observability-on-alz.md).

---

## The one idea that explains most of the failures

On a **governed ALZ**, you are deploying into a subscription that an organization's
management-group policies already control. Two consequences drive almost every error
below:

1. **ALZ policies own certain things** (diagnostic settings, secret validity windows,
   Key Vault purge protection). If your IaC also tries to own them, you get a **race or
   a deny**, not a clean merge.
2. **The deploy identity (a service principal) is less privileged than you are.** It
   often **cannot read management-group-scoped policy** — so any "detect the ALZ and
   adapt" logic that runs as the SP silently false-negatives.

When in doubt on an ALZ: **let the platform own platform concerns, and make your IaC
stand down rather than compete.**

---

## Failure catalog (chronological, with root cause and fix)

Each row is a real error from the first dev deploy. "Class" groups them so you can
recognize the *pattern* the next time, even on a different resource.

### 1. GitHub environment protection rule — HTTP 422

```
gh: Failed to create the environment protection rule. Please ensure the billing
plan supports the required reviewers protection rule. (HTTP 422)
```

- **Class:** plan/repo-type feature gate.
- **Cause:** the bootstrap script created an approval-gate environment with a
  **required-reviewer** protection rule. Required reviewers need **GitHub
  Team/Enterprise or a public repo** — GitHub **Pro on a private personal repo does
  not** support them, even though it supports environments. The 422's "billing plan"
  text is generic; the real refusal is the protection *rule*.
- **Fix:** `Confirm-GitHubEnvironment` now falls back to creating the environment
  **unprotected** on a 422 (with a warning) instead of aborting the whole bootstrap.
  Commit `05ef0c3`. The environment was also renamed `orch` → `hub`.
- **Watch:** on a client repo in a Team org, the gate *will* enforce — which is correct.

### 2. Firewall diagnostic setting — "already exists / needs import"

```
Error: a resource ... azureFirewalls/...azure-firewall already exists - to be
managed via Terraform this resource needs to be imported into the State.
(resource "azurerm_monitor_diagnostic_setting")
```

- **Class:** ALZ owns it; Terraform raced it.
- **Cause:** an ALZ **DeployIfNotExists** policy auto-creates a `setByPolicy-*`
  diagnostic setting on every resource the instant it exists. The firewall took
  **10m37s** to create; Terraform's create-time existence pre-check for *its own*
  diagnostic setting fired during the policy's remediation window → false "already
  exists." A `time_sleep` "stabilization delay" cannot win this race when the target
  takes 10+ minutes.
- **Fix:** **Terraform no longer manages diagnostic settings.** `manage_diagnostic_settings`
  defaults to `false`; the ALZ policy owns diagnostics and logs flow to the central
  workspace. The detection pre-flight is no longer trusted to flip this (see #3).
  Commits `b05efea`, `fcb13ec`. See ADR 0001.

### 3. ALZ diagnostics detection always returned "no policy" (false negative)

```
No ALZ diagnostic-settings policy detected across 1 scope(s).
Decision: manage_diagnostic_settings=true
```

- **Class:** deploy SP lacks the RBAC the logic assumes.
- **Cause:** the detection script walks the subscription's **management-group ancestor
  chain** to find the diagnostics policy. It runs as the **deploy service principal**,
  which **cannot read management groups** — so it scanned only the subscription
  ("1 scope(s)"), found nothing, and defaulted to `true` (manage). Your *user* can see
  the `cbtssandbox*` MGs; the SP cannot. Detection was effectively blind.
- **Fix:** stop depending on detection. The workload `manage_diagnostic_settings`
  default is `false` and the workflow no longer wires it to the pre-flight output.
  Commit `fcb13ec`.
- **Lesson:** any "detect the governance and adapt" logic must run as an identity that
  can actually *read* the governance, or it will fail open. Prefer a safe static
  default over RBAC-dependent detection.

### 4. AI Foundry account — soft-delete 409

```
409 FlagMustBeSetForRestore: An existing resource ... cna-dev-eus2-aif has been
soft-deleted. To restore ... specify 'restore'=true ... or purge it first.
```

- **Class:** prior-crash debris + static name + soft-delete.
- **Cause:** a prior apply created the Cognitive/AIServices account, then a later
  resource failed and the run died. Teardown (`az group delete`) **soft-deleted** the
  account, which **reserves the name** (subscription+region scoped). The static name
  `cna-dev-eus2-aif` then 409s on recreate.
- **Fix (durable):** added provider feature
  `cognitive_account { purge_soft_delete_on_destroy = true }` (dev + prod) so a
  Terraform destroy frees the name. **Dev expediency:** bumped the name to
  `cna-dev-eus2-aif2` to sidestep the existing ghost without a manual purge — **revert
  for prod** (see dev-deploy-workarounds.md). Commit `b814ce3`.
- **Note:** `purge_soft_delete_on_destroy` only fires on `terraform destroy`, **not** on
  the RG-level `az group delete` teardown. The teardown still needs a by-name purge
  step (open follow-up).

### 5. Key Vault secrets — "already exists / needs import" (×5)

```
Error: a resource with the ID "https://cna-dev-scus-kv2.vault.azure.net/secrets/
cna-database-url/..." already exists - to be managed via Terraform ... needs to be
imported into the State.
```

- **Class:** state wiped while Azure resource survived.
- **Cause:** a prior apply wrote the secrets and recorded them in state; a teardown then
  **cleared the state blobs** while the Key Vault (purge-protected, so it survives)
  still held the secrets. Next apply: empty state + existing secrets → "already exists."
- **Fix (one-time):** delete the 5 secrets from the live vault (vault kept) so Terraform
  recreates them. **Prod-safe alternative:** `terraform import` each secret (adopts
  values without rotating). 3 of 5 have `lifecycle { ignore_changes = [value] }`, so
  import preserves their values. See dev-deploy-workarounds.md.
- **Durable:** Key Vault **cannot be purged** (purge protection is enabled by tenant
  policy); `recover_soft_deleted_key_vaults = true` lets a redeploy recover the
  same-named vault. The real prevention is teardown not clearing state while Azure
  resources still exist (open follow-up).

### 6. Container app — empty image variable

```
Error: expected "template.0.container.0.image" to not be an empty string, got
(module.compute.azurerm_container_app.worker / .web)
```

- **Class:** CI plumbing — `$GITHUB_ENV` does not cross jobs.
- **Cause:** the resolved, SHA-pinned image references (`EFFECTIVE_*_IMAGE`) were written
  to `$GITHUB_ENV` in the `policy-gates` and `plan` jobs. `$GITHUB_ENV` is **per-job**.
  The `apply` job's post-platform re-plan read them and got the empty workflow-level
  defaults → `-var="worker_image="`.
- **Fix:** publish the resolved images as **job outputs** from `plan`; the `apply` job
  re-hydrates them via `needs.plan.outputs.*`. Commit `d5be856`.
- **Lesson:** cross-job data flow must use `outputs`, never `$GITHUB_ENV`.

### 7. App Insights KV secret — 403 ForbiddenByGovernancePolicy

```
403 Forbidden ... Secret 'cna-applicationinsights-connection-string' was disallowed
by policy. policyAssignment: Enforce-GR-KeyVault / "Secrets should have the specified
maximum validity period"
```

- **Class:** ALZ deny on secret validity window.
- **Cause:** an ALZ Key Vault guardrail requires secrets to have an expiry within a
  maximum validity period. This secret set a 90-day expiry **and lacked the
  `ignore_changes = [expiration_date]` lifecycle** the other secrets have, so a fresh
  create tripped the deny. (The app code never consumed App Insights anyway.)
- **Fix:** **App Insights removed entirely** (dev + prod) — see ADR 0001. Commit `4ea071a`.
- **Watch (latent):** the same policy governs the *other* secrets' 90-day expiry. If a
  future fresh secret create trips it, set `secret_expiration_date` within the policy's
  allowed window. The policy's exact day limit lives in the `Enforce-GR-KeyVault`
  assignment at the `cbtssandbox-landing-zones` MG (not readable by the deploy SP).

### 8. Foundry validation job — 415 UnsupportedMediaType

```
ERROR: Unsupported Media Type ... The content media type '<null>' is not supported.
Only 'application/json' is supported.
```

- **Class:** `az rest` header default.
- **Cause:** `az rest --method put --body @file` — `az rest` only auto-defaults
  `Content-Type: application/json` when `--body` is an **inline JSON string**. With
  `--body @file` it does **not**, so ARM received a `<null>` media type.
- **Fix:** add `--headers "Content-Type=application/json"`. Commit `0d38e97`.

### 9. Foundry validation job — InvalidRequestContent (JSON parse)

```
InvalidRequestContent: ... unexpected character ... '$'. Path
'properties.template.containers[0].args[1]'
```

- **Class:** heredoc + JSON escaping.
- **Cause:** the job manifest's `args[1]` was written as
  `"echo \\\"\$VAR\\\" | base64 -d | node"`; the unquoted heredoc emitted
  `\\"` which **closes the JSON string early**, leaving a stray `$`.
- **Fix:** drop the unnecessary inner quotes — `"echo \$VAR | base64 -d | node"` (base64
  output has no shell-special chars). Validated by parsing the rendered manifest.
  Commit `cf94be4`.

### 10. Foundry validation job — managed-identity token HTTP 500

```
Managed identity token request failed: HTTP 500: An unexpected error occured while
fetching the AAD Token.
```

- **Class:** fresh-job identity warmup race.
- **Cause:** a freshly-created Container Apps **Job**'s identity sidecar returns a
  transient 500 for the first minute or two while the user-assigned identity warms up.
  The validation node script fetched the token **single-shot** (it only retried DNS),
  so one transient 500 failed everything. The UAI (`cna-dev-scus-id`) is valid and has
  `Cognitive Services User` on Foundry — not an RBAC problem (that would be 403).
- **Fix:** retry the token fetch up to 12×/10s on 5xx/429/network (fail fast on 4xx);
  bump job `replicaTimeout` 300→600s and the poll loop to match. Commit `b509475`.
- **Identity note:** the deployed **web app** uses `SystemAssigned, UserAssigned`
  (both); the **validation job** uses **UserAssigned only** and passes `AZURE_CLIENT_ID`
  to disambiguate. If retries exhaust (500 for ~2 min), it is *not* warmup — investigate
  the job's identity binding, and consider matching the web app's dual-identity config.

---

## Recognizing the patterns (so the next error is faster)

| Symptom | Most likely class | First question to ask |
|---|---|---|
| "already exists / needs import" | state vs. Azure drift, or ALZ policy racing your resource | Did a prior run create it? Does an ALZ policy own it? |
| `403 ...disallowed by policy` / `ForbiddenByGovernancePolicy` | ALZ deny guardrail | Which `policyAssignment` is named in the error? |
| `409 ...soft-deleted ... purge it first` | soft-delete name reservation | Purge the ghost, or bump the name |
| "detect…" logic chose the unsafe default | deploy SP lacks RBAC to read the thing it detects | Can the SP read MG-scoped policy? (usually no) |
| empty var that should be set in a later job | `$GITHUB_ENV` doesn't cross jobs | Is it passed via `needs.<job>.outputs`? |
| `415` / `InvalidRequestContent` from `az rest` | header default / JSON escaping | Is `Content-Type` set? Does the rendered body parse as JSON? |
| transient `500` from a fresh resource's identity/metadata endpoint | sidecar warmup | Is the call retried with backoff? |

---

## Self-hosted runner dependencies (for Ansible / fleet provisioning)

Verified against actual workflow invocations (not a "discovered in the wild" guess). The
authoritative install script is [`scripts/bootstrap-runner.sh`](../scripts/bootstrap-runner.sh);
this table is what an Ansible role must reproduce.

**apt packages:**
```
curl git unzip jq ca-certificates gnupg lsb-release apt-transport-https
software-properties-common python3 python3-pip python3-venv pipx nodejs npm docker.io
```

**Non-apt installs:**

| Tool | Install | Why |
|---|---|---|
| Azure CLI (`az`) | `curl -sL https://aka.ms/InstallAzureCLIDeb \| bash` | 122 invocations across workflows |
| `az` containerapp extension | `az extension add --name containerapp` | 211 DB migration + revision restarts (`az containerapp job`) |
| PowerShell (`pwsh`) | Microsoft apt repo → `apt install powershell` | 330 teardown runs `cleanup-stale-ai-resources.ps1` |

**Installed per-run by the workflows (base must exist, do NOT pre-install):**
`checkov` (via `pipx install` — needs **pipx**), `ruff`, `pip-audit` (via `pip install` —
need **python3-pip**).

**Provided by GitHub Actions per-run — do NOT put on the runner:** Terraform
(`hashicorp/setup-terraform`, which is why `unzip` is needed), buildx, `setup-python`,
the AWS creds action.

**Verified NOT needed:** `aws` CLI (only the creds action runs; no `aws` command is
invoked). `gitleaks` is `continue-on-error` (paid license on private repos) — install
only if you want it to actually run.

### Two gaps even the bootstrap script does not handle (add to Ansible)

1. **pipx PATH for the systemd service.** pipx installs to `~/.local/bin`, which is
   **not** on the runner service's non-login-shell PATH. Workflow 211 works around it by
   resolving the binary via `pipx environment --value PIPX_BIN_DIR`
   ([211 L226-235](../.github/workflows/211-deploy-azure-split.yml#L226-L235)). If
   Ansible pre-installs a pipx tool and expects it on PATH, it won't be — run
   `pipx ensurepath` for `github-runner` and/or set PATH in the systemd unit.
2. **docker group requires a service restart.** After `usermod -aG docker github-runner`,
   the membership only applies after the runner service restarts — Ansible must `notify`
   a handler to restart `actions.runner.*`.

### Multiple runners / fleet notes

- Each runner needs a **unique `--name`** at `config.sh` time — template it
  (`{{ ansible_hostname }}-{{ runner_index }}`), don't hardcode.
- The systemd unit is `actions.runner.<org>-<repo>.<name>.service` — restart handlers
  must use a glob or the templated name.
- Concurrent `terraform` runs against the **same state key** will lock-conflict — that's
  a workflow-concurrency concern, not a runner-provisioning one. Image builds use SHA
  tags, which is safe for concurrency.

---

## Pre-flight checklist for the next environment (prod / client ALZ)

- [ ] Confirm `manage_diagnostic_settings` is `false` (ALZ owns diagnostics).
- [ ] Confirm App Insights is absent (removed in ADR 0001).
- [ ] Check for a soft-deleted Cognitive account under the prod name and purge it, or
      confirm the name is free (`az cognitiveservices account list-deleted`).
- [ ] Revert the dev-only `-aif2` name bump back to the prod naming.
- [ ] For prod KV-secret collisions, prefer `terraform import` over delete (don't rotate
      live secrets).
- [ ] Verify the runner has the full dependency set above (especially `az`, the
      containerapp extension, and `pwsh`).
- [ ] Know your ALZ Key Vault secret max-validity window; ensure `secret_expiration_date`
      fits it.
- [ ] If the repo is in a Team org, the `hub` approval gate will enforce — confirm
      reviewers are set.

---

_First compiled 2026-06-29 from the initial end-to-end dev deploy. Update as new ALZ
failure modes are discovered._
