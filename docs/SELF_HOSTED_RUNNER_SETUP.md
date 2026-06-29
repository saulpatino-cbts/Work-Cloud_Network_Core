# Setting Up a Self-Hosted GitHub Actions Runner on a VPS

A guide to configuring a self-hosted runner on a remote VPS for CI/CD workflows, including connectivity validation, service management, and common gotchas discovered running real workflows.

## Overview

GitHub Actions runners can execute on GitHub-hosted infrastructure (`ubuntu-latest`, etc.) or on your own hardware via self-hosted runners. This guide walks through setting up a self-hosted runner on a VPS and validates all required network connectivity.

**When to use self-hosted runners:**
- Your workflows need access to private infrastructure (databases, internal APIs, on-prem resources)
- You want faster, cheaper builds (no GitHub Actions minute usage)
- You need persistent state or large dependency caches
- You're running resource-intensive workloads (Terraform deploys, Docker builds)

---

## TL;DR — Bootstrap Script

Skip the manual steps. Run this on your VPS as root to install everything in one shot:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR-ORG/YOUR-REPO/main/scripts/bootstrap-runner.sh | bash
```

Or copy [`scripts/bootstrap-runner.sh`](../scripts/bootstrap-runner.sh) to your VPS and run it. See the [Bootstrap Script](#bootstrap-script) section for details.

---

## Prerequisites

- A VPS running Ubuntu 20.04+ with SSH access
- GitHub repository with admin access (to register the runner)
- A non-root user on the VPS — runners refuse to run as root
- Outbound HTTPS access to GitHub, Azure, and Docker Hub

---

## Step 1: Install System Dependencies

Before anything else, install all packages the runner needs. Missing packages will cause cryptic workflow failures mid-run.

```bash
sudo apt-get update && sudo apt-get install -y \
    curl \
    git \
    unzip \
    jq \
    docker.io \
    python3 \
    python3-pip \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release
```

**⚠️ Did You Know?** `ubuntu-latest` on GitHub-hosted runners comes pre-loaded with dozens of tools. Your self-hosted VPS starts bare. Every tool your workflows call — `unzip`, `python3`, `docker`, `jq` — must be explicitly installed. You will discover missing packages one workflow failure at a time unless you install them upfront.

### Known Required Packages (discovered in the wild)

| Package | Why Needed |
|---------|-----------|
| `unzip` | `hashicorp/setup-terraform` action extracts Terraform binary with unzip |
| `docker.io` | Docker builds, image pulls/pushes |
| `python3` | Workflow step summaries, CI scripts |
| `python3-pip` | Installing Python tools (e.g. `checkov`) |
| `curl` | Connectivity checks, downloading binaries |
| `git` | `actions/checkout` requires git |
| `jq` | JSON parsing in shell scripts |

> This list grows as you run more workflows. See the [bootstrap script](../scripts/bootstrap-runner.sh) — it's the living source of truth for what this runner needs.

---

## Step 2: Create a Dedicated Non-Root User

**⚠️ Did You Know?** The GitHub Actions Runner explicitly refuses to run as `root`. This is a security boundary — even `sudo ./config.sh` fails with "Must not run with sudo". You must use a dedicated unprivileged user.

```bash
# Create the runner user
useradd -m -s /bin/bash github-runner

# Add to the docker group so it can talk to the Docker daemon
usermod -aG docker github-runner
```

**⚠️ Did You Know?** Adding a user to the `docker` group takes effect on the **next login or service restart** — not immediately. If you add the group after the runner service is already running, you must restart the service for it to pick up the new group membership.

---

## Step 3: Validate Network Connectivity

Before configuring the runner, verify your VPS can reach all required endpoints:

```bash
#!/bin/bash

echo "=== GitHub Actions Runner Connectivity Check ==="
echo ""

check_endpoint() {
    local name="$1"
    local url="$2"
    echo -n "Checking $name ... "
    if curl -s -m 5 -I "$url" > /dev/null 2>&1; then
        echo "✓ OK"
        return 0
    else
        echo "✗ FAILED"
        return 1
    fi
}

failed=0

check_endpoint "GitHub API"          "https://api.github.com"            || failed=1
check_endpoint "Azure Management"    "https://management.azure.com"      || failed=1
check_endpoint "Microsoft Entra ID"  "https://login.microsoftonline.com" || failed=1
check_endpoint "Docker Hub"          "https://index.docker.io"           || failed=1
check_endpoint "Docker Registry"     "https://registry.hub.docker.com"   || failed=1

echo ""
if [ $failed -eq 0 ]; then
    echo "✓ All connectivity checks passed"
    exit 0
else
    echo "✗ Some endpoints are unreachable — check firewall rules"
    exit 1
fi
```

Save as `check-connectivity.sh`, make executable, and run:

```bash
chmod +x check-connectivity.sh
./check-connectivity.sh
```

If any endpoint fails:
- **GitHub API** — Check outbound HTTPS; may be blocked by corporate firewall
- **Azure Management** — Ensure Azure service endpoints are reachable
- **Docker Hub** — Required for image pulls and pushes
- **Entra ID** — Required for OIDC token exchange for Azure auth

---

## Step 4: Download and Configure the Runner

Get a registration token from GitHub:

1. Go to **Settings** → **Actions** → **Runners** → **New self-hosted runner**
2. Select **Linux** and **x64**
3. Copy the registration token — **valid for ~1 hour only**

```bash
# Switch to the runner user
su - github-runner

mkdir -p ~/actions-runner && cd ~/actions-runner

# Download (check https://github.com/actions/runner/releases for latest)
curl -o actions-runner-linux-x64-2.335.1.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.335.1/actions-runner-linux-x64-2.335.1.tar.gz

# Verify checksum (copy from GitHub release page)
echo "4ef2f252585f8ae477f1fe1e346db76d2f3ebf03824c2ddd1973a2819bf6c8cf  actions-runner-linux-x64-2.335.1.tar.gz" | shasum -a 256 -c

tar xzf ./actions-runner-linux-x64-2.335.1.tar.gz

# Configure (token expires in ~1 hour — don't dawdle)
./config.sh --url https://github.com/YOUR-ORG/YOUR-REPO --token YOUR_TOKEN_HERE
```

When prompted:
- **Runner group:** Enter for "Default"
- **Runner name:** Give it a descriptive name (e.g. `vps-runner`)
- **Labels:** Enter to skip (default: `self-hosted`, `Linux`, `X64`)
- **Work folder:** Enter for `_work`

**⚠️ Token Expiry Gotcha:** If registration fails with a 404 error, your token expired. Go back to GitHub Settings, generate a fresh token, and re-run `./config.sh`.

---

## Step 5: Install as a Systemd Service

**Do not use `./run.sh` in production.** It dies when your SSH session closes. Install it as a systemd service instead.

```bash
# Back as root (exit from github-runner user first)
exit

cd /home/github-runner/actions-runner

# Install the service
sudo ./svc.sh install github-runner

# Start it
sudo ./svc.sh start

# Verify it's running
sudo ./svc.sh status
```

**Expected output:**
```
● actions.runner.YOUR-ORG-YOUR-REPO.vps-runner.service
     Loaded: loaded (/etc/systemd/system/actions.runner...service; enabled)
     Active: active (running) since ...
```

**⚠️ Did You Know?** `svc.sh` only exists after you've run `./config.sh`. If you try to run it before configuration, it won't be there. Always configure first, then install as a service.

**⚠️ Did You Know?** `svc.sh` must be run as root (or with sudo) from **outside** the `github-runner` user session — not as `github-runner` itself. The pattern is:
```bash
su - github-runner    # configure the runner
exit                  # back to root
sudo ./svc.sh install # install service as root
```

---

## Step 6: Service Management Reference

```bash
# Start
sudo ./svc.sh start
# or
sudo systemctl start actions.runner.YOUR-ORG-YOUR-REPO.vps-runner

# Stop
sudo ./svc.sh stop

# Restart (required after usermod -aG docker github-runner)
sudo systemctl restart actions.runner.YOUR-ORG-YOUR-REPO.vps-runner

# Status
sudo ./svc.sh status

# Live logs
sudo journalctl -u actions.runner.* -f

# Enable on boot (svc.sh install does this automatically)
sudo systemctl enable actions.runner.YOUR-ORG-YOUR-REPO.vps-runner

# Uninstall service
sudo ./svc.sh uninstall
```

**After any `usermod` change** (e.g. adding `docker` group), always restart the service:
```bash
sudo usermod -aG docker github-runner
sudo systemctl restart actions.runner.*
```

---

## Step 7: Update Your Workflows

In every `.github/workflows/*.yml`, change:

```yaml
runs-on: ubuntu-latest
```

to:

```yaml
runs-on: self-hosted
```

Or target by label:

```yaml
runs-on: [self-hosted, vps]
```

---

## Bootstrap Script

The [`scripts/bootstrap-runner.sh`](../scripts/bootstrap-runner.sh) script automates everything above. It is the **living log** of every package and configuration this runner needs — update it each time a new workflow dependency is discovered.

```bash
# Run as root on a fresh VPS
sudo bash scripts/bootstrap-runner.sh
```

It will:
1. Install all required system packages
2. Install Docker and add `github-runner` to the docker group
3. Create the `github-runner` user
4. Run connectivity checks
5. Print next steps for manual registration (token required)

---

## Common Issues and Fixes

### "Must not run with sudo"
Runner refuses to run as root. Use `su - github-runner` and run `./config.sh` from there.

### 404 on runner registration
Token expired (1 hour limit). Generate a new one in GitHub Settings → Actions → Runners.

### "Unable to locate executable file: unzip"
`unzip` not installed. Run `sudo apt-get install -y unzip` on the VPS.

### "permission denied while trying to connect to the Docker socket"
`github-runner` user not in `docker` group. Fix:
```bash
sudo usermod -aG docker github-runner
sudo systemctl restart actions.runner.*
```

### "python: command not found"
Ubuntu ships `python3`, not `python`. Workflow scripts must use `python3`, not `python`.

### Workflow stalls "Waiting for a runner"
Runner service isn't running. Check:
```bash
sudo systemctl status actions.runner.*
sudo journalctl -u actions.runner.* -f
```

### "Terraform init fails — permission denied on tfstate"
Runner's public IP isn't whitelisted on Azure Key Vault or Storage firewall. Your workflows should dynamically add/remove the runner IP — or use OIDC with private endpoints.

---

## Connectivity Requirements Summary

| Target | Port | Used For |
|--------|------|----------|
| `api.github.com` | 443 | Runner registration, job polling |
| `index.docker.io`, `registry.hub.docker.com` | 443 | Docker image pulls/pushes |
| `management.azure.com` | 443 | Terraform, Azure CLI |
| `login.microsoftonline.com` | 443 | OIDC token exchange |
| `*.vault.azure.net` | 443 | Azure Key Vault secrets |

---

## References

- [GitHub Actions — Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [GitHub Actions — Adding self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners)
- [GitHub Actions — Using self-hosted runners in a workflow](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/using-self-hosted-runners-in-a-workflow)

---

**Happy CI/CD-ing!** 🚀
