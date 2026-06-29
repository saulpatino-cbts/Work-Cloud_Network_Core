# Setting Up a Self-Hosted GitHub Actions Runner on a VPS

A guide to configuring a self-hosted runner on a remote VPS for CI/CD workflows, including connectivity validation and common gotchas.

## Overview

GitHub Actions runners can execute on GitHub-hosted infrastructure (ubuntu-latest, etc.) or on your own hardware via self-hosted runners. This guide walks through setting up a self-hosted runner on a VPS and validates all required network connectivity.

**When to use self-hosted runners:**
- Your workflows need access to private infrastructure (databases, internal APIs, on-prem resources)
- You want faster, cheaper builds (no GitHub Actions minute usage)
- You need persistent state or large dependency caches
- You're running resource-intensive workloads (Terraform deploys, Docker builds)

## Prerequisites

- A VPS or machine with SSH access
- GitHub repository with admin access (to register the runner)
- A non-root user on the VPS (runners refuse to run as root)
- Outbound HTTPS access to GitHub, Azure, and Docker Hub

## Step 1: Create a Dedicated Non-Root User

**⚠️ Did You Know?** The GitHub Actions Runner explicitly refuses to run as `root`. This is a security boundary — even if you try `sudo ./config.sh`, it will fail with "Must not run with sudo". You must create a dedicated unprivileged user.

SSH into your VPS as root (or a user with `sudo` privileges):

```bash
# Create a new user for the runner
useradd -m -s /bin/bash github-runner

# Switch to that user
su - github-runner
```

This user will own the runner process and all artifacts it generates.

## Step 2: Download and Verify the Runner

GitHub provides pre-built runner packages. Always verify the SHA checksum.

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download the latest Linux x64 runner
# (Check https://github.com/actions/runner/releases for the latest version)
curl -o actions-runner-linux-x64-2.335.1.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.335.1/actions-runner-linux-x64-2.335.1.tar.gz

# Verify the checksum (copy from GitHub's release page)
echo "4ef2f252585f8ae477f1fe1e346db76d2f3ebf03824c2ddd1973a2819bf6c8cf  actions-runner-linux-x64-2.335.1.tar.gz" | shasum -a 256 -c

# Extract
tar xzf ./actions-runner-linux-x64-2.335.1.tar.gz
```

**⚠️ Checksum Mismatch?** If the SHA doesn't match, the download was corrupted or the release was re-uploaded. GitHub usually provides updated checksums — fetch them from the release page.

## Step 3: Validate Network Connectivity

Before configuring the runner, ensure your VPS can reach GitHub, Azure, and Docker Hub. Use this connectivity check script:

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

check_endpoint "GitHub API" "https://api.github.com" || failed=1
check_endpoint "Azure Management" "https://management.azure.com" || failed=1
check_endpoint "Microsoft Entra ID" "https://login.microsoftonline.com" || failed=1
check_endpoint "Docker Hub" "https://index.docker.io" || failed=1
check_endpoint "Docker Registry" "https://registry.hub.docker.com" || failed=1

echo ""
if [ $failed -eq 0 ]; then
    echo "✓ All connectivity checks passed"
    exit 0
else
    echo "✗ Some endpoints are unreachable — check firewall rules"
    exit 1
fi
```

Save this as `check-connectivity.sh`, make it executable, and run it:

```bash
chmod +x check-connectivity.sh
./check-connectivity.sh
```

**Expected output:**
```
=== GitHub Actions Runner Connectivity Check ===

Checking GitHub API ... ✓ OK
Checking Azure Management ... ✓ OK
Checking Microsoft Entra ID ... ✓ OK
Checking Docker Hub ... ✓ OK
Checking Docker Registry ... ✓ OK

✓ All connectivity checks passed
```

If any endpoint fails:
- **GitHub API** — Check outbound HTTPS from your VPS; may be blocked by corporate firewall
- **Azure Management** — Ensure Azure service endpoints are reachable; check firewall rules
- **Docker Hub** — Required for image pulls and pushes; may need proxy configuration
- **Entra ID** — Required for OIDC token exchange; essential for Azure authentication

## Step 4: Register the Runner

Get a registration token from GitHub:

1. Go to **Settings** → **Actions** → **Runners** → **New self-hosted runner**
2. Select **Linux** and **x64**
3. Copy the registration token (valid for ~1 hour)

**⚠️ Token Expiry Gotcha:** If setup stalls, the token expires and registration fails with a 404 error. Regenerate a fresh token and retry.

Configure the runner (as the non-root `github-runner` user):

```bash
./config.sh --url https://github.com/YOUR-ORG/YOUR-REPO --token YOUR_TOKEN_HERE
```

When prompted:
- **Runner group:** Press Enter for "Default"
- **Runner name:** Give it a descriptive name (e.g., `vps-runner`, `prod-runner`)
- **Labels:** Press Enter to skip (or add custom labels like `docker-capable`, `prod`)
- **Work folder:** Press Enter for `_work` (standard location)

**Example interaction:**
```
√ Connected to GitHub

# Runner Registration

Enter the name of the runner group to add this runner to: [press Enter for Default]

Enter the name of runner: [press Enter for srv939861] vps-runner

This runner will have the following labels: 'self-hosted', 'Linux', 'X64'
Enter any additional labels (ex. label-1,label-2): [press Enter to skip]

√ Runner successfully added
```

## Step 5: Run the Runner

### Option A: Foreground (Testing)

```bash
./run.sh
```

This runs in the foreground and you'll see live job output. Useful for debugging. Stop with `Ctrl+C`.

### Option B: Background Service (Recommended for Production)

Install as a systemd service so the runner starts automatically and survives reboots:

```bash
# Install (as the github-runner user, or use sudo from another account)
sudo ./svc.sh install

# Start
sudo ./svc.sh start

# Check status
sudo ./svc.sh status

# View logs (if needed)
sudo journalctl -u actions.runner.YOUR-ORG-YOUR-REPO.vps-runner -f
```

## Step 6: Update Your Workflows

In your `.github/workflows/*.yml` files, change:

```yaml
runs-on: ubuntu-latest
```

to:

```yaml
runs-on: self-hosted
```

Or use labels for finer control:

```yaml
runs-on: [self-hosted, vps]
runs-on: [self-hosted, docker-capable]
```

## Testing the Runner

Dispatch a simple workflow to verify the runner picks up jobs:

```yaml
name: Test Self-Hosted Runner

on: [workflow_dispatch]

jobs:
  test:
    runs-on: self-hosted
    steps:
      - name: Print runner info
        run: |
          echo "Hostname: $(hostname)"
          echo "OS: $(uname -a)"
          echo "Docker: $(docker --version)"
      
      - name: Checkout
        uses: actions/checkout@v6
      
      - name: List files
        run: ls -la
```

Go to **Actions** → **Test Self-Hosted Runner** → **Run workflow** and watch it execute on your VPS.

## Common Issues and Fixes

### "Must not run with sudo"

**Problem:** You tried to run `sudo ./config.sh`.

**Solution:** The runner refuses to run as root. Use a non-root user:
```bash
su - github-runner
./config.sh --url https://github.com/ORG/REPO --token TOKEN
```

### "Http response code: NotFound from 'POST https://api.github.com/actions/runner-registration'"

**Problem:** The registration token expired (valid for ~1 hour).

**Solution:** Generate a fresh token in GitHub Settings and re-run `./config.sh`.

### "Connectivity check fails for Docker Hub"

**Problem:** Your VPS can't reach Docker Hub (firewall, proxy, DNS).

**Solution:**
- Check firewall rules: `curl -v https://index.docker.io`
- If behind a corporate proxy, configure Docker proxy in `/etc/docker/daemon.json`
- Verify DNS: `nslookup index.docker.io`

### Workflow stalls "Waiting for a runner to pick up this job"

**Problem:** The runner isn't listening for jobs.

**Solutions:**
- Check runner status: `sudo ./svc.sh status`
- Check logs: `sudo journalctl -u actions.runner.* -f`
- Verify GitHub connectivity: run the connectivity check script
- Restart the runner: `sudo ./svc.sh stop && sudo ./svc.sh start`

### "Terraform init fails with 'permission denied' on tfstate storage account"

**Problem:** The runner's public IP isn't whitelisted on your Azure Firewall or Key Vault network rules.

**Solution:**
- Your CI workflow should dynamically add/remove the runner's IP from Key Vault firewall rules
- Or: Open Azure resources to the runner's IP range (if static)
- Or: Use Azure OIDC + private endpoints (no IP whitelisting needed)

## Connectivity Requirements Summary

| Target | Port | Used For |
|--------|------|----------|
| `api.github.com` | 443 | Runner registration, job polling |
| `index.docker.io`, `registry.hub.docker.com` | 443 | Docker image pulls/pushes |
| `management.azure.com` | 443 | Terraform deploys, Azure resource management |
| `login.microsoftonline.com` | 443 | OIDC token exchange for Azure auth |
| `*.vault.azure.net` | 443 | Azure Key Vault access (for secrets) |

If any of these are blocked, workflows will fail at the relevant step.

## Performance Tips

1. **Use SHA-tagged images, not `:latest`** — Immutable tags are faster and more reliable than pulling the floating latest tag every run
2. **Cache Docker layers** — Use `cache-from: type=gha` in docker/build-push-action
3. **Pin action versions to SHA digests** — Faster than fetching by semver tag
4. **Run multiple concurrent jobs** — The runner can queue jobs and execute them in parallel (disk/CPU dependent)

## Maintenance

### Checking Runner Status

```bash
# Via GitHub UI
Settings > Actions > Runners > [your-runner-name]

# Via systemd (if running as service)
sudo systemctl status actions.runner.YOUR-ORG-YOUR-REPO.vps-runner

# Via logs
sudo journalctl -u actions.runner.* -f
```

### Updating the Runner

```bash
# Stop the service
sudo ./svc.sh stop

# Remove old version
cd ~/actions-runner
rm -rf *

# Download and extract new version (repeat Step 2)
curl -o actions-runner-linux-x64-VERSION.tar.gz ...
tar xzf actions-runner-linux-x64-VERSION.tar.gz

# Reconfigure with existing token (or new one if expired)
./config.sh --url https://github.com/ORG/REPO --token TOKEN

# Restart
sudo ./svc.sh start
```

### Removing the Runner

```bash
# Uninstall the service
sudo ./svc.sh uninstall

# Remove from GitHub (optional, but recommended)
# Go to Settings > Actions > Runners and click the trash icon
```

## References

- [GitHub Actions - Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [GitHub Actions - Creating and configuring self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners)
- [GitHub Actions - Using self-hosted runners in a workflow](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/using-self-hosted-runners-in-a-workflow)

---

**Happy CI/CD-ing!** 🚀
