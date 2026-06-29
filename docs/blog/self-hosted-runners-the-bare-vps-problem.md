# Self-Hosted Runners: Every Tool You Forgot You Depend On

*2026-06-29 · Field notes on provisioning a GitHub Actions runner for the CNA pipeline*

`ubuntu-latest` is a lie of omission. Not a malicious one — but when you write a workflow
against GitHub-hosted runners, you're standing on a machine pre-loaded with *dozens* of
tools: the Azure CLI, Docker, Node, Python, jq, PowerShell, a hundred others. You never
declared them because you never had to. They were just… there.

Then you move to a self-hosted runner on a bare VPS to reach private infrastructure, and
the floor disappears. Every implicit dependency becomes an explicit one — and you
discover them **one cryptic mid-workflow failure at a time.**

This is the story of mapping CNA's *actual* runner dependency surface, and the subtle
traps that a naive "install the obvious packages" approach leaves behind.

## "It worked on ubuntu-latest" is not a dependency list

Our first runner doc had a package table titled *"discovered in the wild."* That phrase
is the whole problem. A dependency list built from past failures only contains the
dependencies that have *already* bitten you. The ones waiting in an un-run code path are
invisible.

So instead of trusting the list, we **derived** it — by grepping every workflow and CI
script for every external command they invoke. The result was humbling. The "obvious"
list (curl, git, jq, docker, python3) was about half the real surface.

## The tools that don't come from apt

The expensive gaps weren't missing apt packages — those fail loudly and obviously
("`unzip`: command not found"). The expensive gaps were the tools that **aren't in apt at
all**, so you don't even think to list them:

- **Azure CLI** — 122 invocations across the workflows. Installed via Microsoft's script
  (`curl https://aka.ms/InstallAzureCLIDeb | bash`), not `apt install azure-cli`.
- **The `az containerapp` extension** — core `az` does *not* include the `containerapp`
  command group. Our deploy runs `az containerapp job ...` for DB migrations and revision
  restarts; without the extension it fails with "unrecognized arguments: job." You install
  it separately (`az extension add --name containerapp`), and it's easy to forget because
  it looks like part of `az`.
- **PowerShell (`pwsh`)** — our teardown runs a `.ps1` cleanup script. On Linux, `pwsh`
  comes from Microsoft's package repo, not apt defaults.
- **Node and npm** — our build runs `npm audit` *on the runner* (not just inside the
  Docker build), in the web app directory.

Every one of these would fail deep into a workflow, after minutes of setup, with an error
that doesn't say "your runner is missing a tool" — it says "unrecognized arguments" or
"command not found" buried in a step you didn't suspect.

## The trap that survives even a "complete" install: PATH

Here's the one that's genuinely sneaky, because the tool *is* installed and still doesn't
work.

We install Python CLI tools (checkov, ruff, pip-audit) via **pipx**, partly because
Ubuntu 24.04 enforces PEP 668 and refuses system-wide `pip install`. pipx drops its
binaries into `~/.local/bin`. On an interactive login that's on your PATH. But the GitHub
Actions runner runs as a **systemd service** — a **non-login shell** — and `~/.local/bin`
is **not** on its PATH.

So `pipx install checkov` succeeds, and then `checkov` "isn't found" when the workflow
runs it. The fix our deploy uses is to never assume PATH at all — it resolves the binary
explicitly:

```bash
pipx install checkov --force --quiet
PIPX_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR)"
CHECKOV="$PIPX_BIN_DIR/checkov"
```

The lesson generalizes: **a tool being installed and a tool being on the service's PATH
are two different facts.** Provisioning has to guarantee both, or workflows have to stop
assuming PATH.

## The other quiet one: group membership needs a restart

You add the runner user to the `docker` group so it can talk to the daemon. Correct. But
group membership only takes effect on the **next login or service restart** — and if your
runner service is already running, the first Docker step fails with "permission denied
while trying to connect to the Docker socket," even though `groups github-runner` clearly
shows `docker`.

The membership is right. The *running process* just hasn't picked it up. You have to
restart the service. In Ansible terms: the `usermod` task must **notify a handler** that
restarts `actions.runner.*`, or you'll provision a runner that looks correct and fails on
the first build.

## What you should NOT install (knowing the absence matters too)

Half of a good dependency audit is ruling things *out* so you don't cargo-cult:

- **Terraform** is not a runner dependency — the `hashicorp/setup-terraform` action
  installs it per-run. (It *does* need `unzip`, which is why `unzip` is on the list and
  Terraform isn't.)
- **The AWS CLI** is not needed. We use the AWS *credentials* action, but no step ever
  invokes `aws`. We confirmed by grep before adding a package nobody calls.
- **gitleaks** runs `continue-on-error` (it needs a paid license on private repos), so
  it's effectively optional — install it only if you want it to actually do something.

Buildx, the Python toolchain pinning, the GitHub App token — all provided by actions
per-run. Putting them in your provisioning is wasted effort and drift.

## The real deliverable: declarative, not discovered

The endpoint of all this is the realization that a self-hosted runner's dependencies
should be **declarative infrastructure**, derived from what the pipeline invokes — not a
markdown table that grows one incident at a time.

We're moving ours into Ansible. The role has to reproduce:

1. the full apt set (including the non-obvious `pipx`, `python3-venv`, `nodejs`/`npm`),
2. the non-apt installs (Azure CLI, the containerapp extension, pwsh),
3. **pipx PATH** for the systemd service (`pipx ensurepath` + unit PATH),
4. a **docker-group handler** that restarts the runner service,
5. a **templated, unique runner name** per host (for fleets),

…and explicitly *not* install the things the actions provide.

The difference between this and "install the obvious packages" is the difference between a
runner that onboards in one `ansible-playbook` run and a runner that onboards over a week
of failed workflows. Derive the list from the pipeline. Verify the absences. Don't trust
"it worked on ubuntu-latest."

---

*The verified dependency table, install commands, and fleet notes live in
[alz-deployment-runbook.md § runner dependencies](../alz-deployment-runbook.md#self-hosted-runner-dependencies-for-ansible--fleet-provisioning).
The decision record:
[ADR 0002](../adr/0002-self-hosted-runner-dependency-management.md). The current install
script: [`scripts/bootstrap-runner.sh`](../../scripts/bootstrap-runner.sh).*
