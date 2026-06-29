# ADR 0002: Self-Hosted GitHub Actions Runner Dependency Management

- **Status:** Accepted
- **Date:** 2026-06-29
- **Deciders:** Platform/DevOps (CNA)
- **Related:** [SELF_HOSTED_RUNNER_SETUP.md](../SELF_HOSTED_RUNNER_SETUP.md),
  [`scripts/bootstrap-runner.sh`](../../scripts/bootstrap-runner.sh),
  [blog: self-hosted runners — the bare-VPS problem](../blog/self-hosted-runners-the-bare-vps-problem.md),
  [alz-deployment-runbook.md](../alz-deployment-runbook.md)

## Context

CNA's CI/CD runs on a **self-hosted GitHub Actions runner** on a VPS, chosen because the
pipeline needs to reach private infrastructure (Azure Key Vault / Storage behind
firewalls, private endpoints) and to avoid GitHub-hosted minute costs for
Terraform/Docker-heavy workflows.

Unlike `ubuntu-latest`, a self-hosted VPS starts **bare**. Every tool the workflows
assume is present must be explicitly provisioned. During the first end-to-end deploy this
surfaced as a series of mid-workflow failures — each a missing tool discovered at runtime
(`unzip`, then the `az containerapp` extension, then `pwsh`, …). The dependency list was
maintained reactively ("discovered in the wild"), which by construction only ever
contained dependencies that had already caused a failure.

Three classes of provisioning hazard were identified:

1. **Non-apt tools** that are easy to omit because they aren't `apt install <name>`:
   Azure CLI, the `az containerapp` extension, PowerShell (`pwsh`).
2. **PATH for the systemd service:** pipx installs CLI tools to `~/.local/bin`, which is
   not on the runner *service's* non-login-shell PATH. Tools install successfully and
   then "aren't found."
3. **Deferred group membership:** adding the runner user to `docker` only takes effect
   after a service restart; without it, the first Docker step fails on the socket.

## Decision

**1. The runner dependency set is derived from what the pipeline invokes, and treated as
declarative infrastructure** — not a reactively-grown list. The authoritative derivation
(verified by grepping every workflow and CI script) is recorded in
[alz-deployment-runbook.md](../alz-deployment-runbook.md#self-hosted-runner-dependencies-for-ansible--fleet-provisioning):

- **apt:** `curl git unzip jq ca-certificates gnupg lsb-release apt-transport-https
  software-properties-common python3 python3-pip python3-venv pipx nodejs npm docker.io`
- **non-apt:** Azure CLI (`aka.ms/InstallAzureCLIDeb`), the `az containerapp` extension,
  PowerShell (`pwsh`, Microsoft apt repo).
- **per-run, installed by workflows (base must exist, not pre-installed):** `checkov`
  (pipx), `ruff`, `pip-audit` (pip).
- **provided by GitHub Actions per-run, NOT provisioned:** Terraform
  (`setup-terraform`), buildx, `setup-python`, the AWS creds action.
- **explicitly not needed:** `aws` CLI (no `aws` command is invoked), `gitleaks`
  (`continue-on-error`, paid on private repos).

**2. Provisioning must guarantee tool *reachability*, not just installation.**

- Run `pipx ensurepath` for the runner user **and** ensure `~/.local/bin` is on the
  systemd service PATH; or workflows resolve pipx tools via
  `pipx environment --value PIPX_BIN_DIR` (workflow 211 already does this).
- The `usermod -aG docker` step must trigger a **restart of the runner service** so group
  membership takes effect.

**3. The medium-term target is an Ansible role**, not the bash bootstrap script, so the
runner set is idempotent and fleet-deployable. `bootstrap-runner.sh` remains the
interim/source-of-truth until the role exists; the Ansible role must reproduce the set
above plus the two reachability fixes.

**4. Fleet/multi-runner provisioning rules:**

- Each runner registers with a **unique, templated `--name`**
  (e.g. `{{ ansible_hostname }}-{{ runner_index }}`); never hardcoded.
- systemd unit / restart handlers reference the service by glob or templated name
  (`actions.runner.<org>-<repo>.<name>.service`).
- Image builds use SHA-pinned tags (safe under concurrency); concurrent Terraform against
  the same state key is a **workflow-concurrency** concern handled in the workflows, not a
  provisioning concern.

## Consequences

### Positive

- A new runner onboards in a single provisioning run, not over a week of failed workflows.
- The dependency set is auditable and reproducible; absences are documented so nobody
  cargo-cults `aws`/Terraform onto the runner.
- The two non-obvious hazards (pipx PATH, docker-group restart) are captured as explicit
  provisioning steps rather than tribal knowledge.

### Negative / trade-offs

- **Maintenance coupling:** when a workflow adds a new external tool, the Ansible role (and
  the runbook table) must be updated in the same change. Mitigation: the runbook documents
  the grep-derivation method so the audit is repeatable, and CI scripts should prefer tools
  already in the set.
- **Two sources during transition:** `bootstrap-runner.sh` and the (future) Ansible role
  can drift until the script is retired. Mitigation: the script's header is marked as the
  interim source-of-truth and points at this ADR.
- **Self-hosted ownership cost:** OS patching, runner version upgrades, and security of
  the VPS are now our responsibility (vs. GitHub-managed ephemeral runners). Accepted as
  the cost of private-network reach.

### Security note

The runner holds Azure OIDC trust and Docker Hub credentials and reaches private
infrastructure. A persistent self-hosted runner is a higher-value target than an ephemeral
GitHub-hosted one. Provisioning must keep the runner user unprivileged (the runner refuses
to run as root), scope its Azure identity minimally, and the VPS must be patched. This is
a consequence of the self-hosted choice, accepted for the private-network requirement.

## Alternatives considered

- **GitHub-hosted runners (`ubuntu-latest`).** Rejected: cannot reach private endpoints /
  firewalled Key Vault and Storage without additional networking (e.g. a self-hosted
  network path anyway), and incurs per-minute cost for heavy Terraform/Docker jobs.
- **Container-based / ephemeral self-hosted runners (fresh image per job).** Not adopted
  now (more infrastructure to build), but it is the natural evolution: it would make the
  dependency set a Dockerfile and eliminate both the PATH and group-membership-restart
  hazards. Revisit when fleet size or supply-chain requirements justify it.
- **Keep the reactive "discovered in the wild" list.** Rejected: by construction it only
  contains already-encountered failures and guarantees onboarding-by-incident.

## Implementation status

- Interim: [`scripts/bootstrap-runner.sh`](../../scripts/bootstrap-runner.sh) installs the
  full set (apt, Azure CLI + containerapp extension, pwsh, nodejs/npm, pipx) and creates
  the runner user. **Gaps to close in the Ansible role:** `pipx ensurepath` / service PATH,
  and a docker-group→service-restart handler.
- Target: an Ansible role reproducing this ADR, with templated runner registration for
  fleets.
