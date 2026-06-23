# Devil's Advocate Review - Best Practice Violations

The following issues were identified during a strict Devil's Advocate review of `.github/workflows/210-deploy-azure.yml`. They do not currently break the pipeline but violate Microsoft/GitHub recommended best practices and should be refactored:

## ~~1. Key Vault Firewall Circumvention~~ (Fixed)
**Location:** `210-deploy-azure.yml` > `Ensure Key Vault is reachable during Terraform`
**Issue:** The pipeline temporarily sets `--public-network-access Enabled` with a default `Allow` action to push initial values. This exposes the Key Vault to the public internet temporarily.
**Recommendation:** Use a self-hosted GitHub runner deployed inside the VNet, OR dynamically authorize only the GitHub Runner's exact public IP via `az keyvault network-rule add` and remove it immediately after the step.
*(Fixed by dynamically adding/removing runner IP)*

## 2. Fragile Private IP Guessing
**Location:** `210-deploy-azure.yml` > `Ensure PostgreSQL private DNS A record`
**Issue:** A python snippet calculates `list(net.hosts())[3]` to blindly guess the PostgreSQL Flexible Server's private IP. This relies on undocumented Azure behavior where the server claims the 4th IP address of the delegated subnet.
**Recommendation:** Wait for Azure to automatically synchronize the Private DNS zone, or use an Azure Private DNS Resolver, or manage the DNS record natively in Terraform rather than hacking it via CLI.

## 3. GitHub Variables Mutation in Pipeline
**Location:** `210-deploy-azure.yml` > `Update GitHub Variables from Terraform outputs`
**Issue:** The pipeline uses `gh variable set` to update repository variables. CI/CD pipelines should be read-only consumers of variables to prevent race conditions during concurrent deployments.
**Recommendation:** Manage environment variables centrally via a GitOps config repository or use the Terraform GitHub Provider.

## 4. Certificate Import Drift
**Location:** `210-deploy-azure.yml` > `Query certificate monitoring and trigger renewal workflow`
**Issue:** The workflow attempts `az keyvault certificate import` outside of Terraform. Terraform will report drift on the Key Vault certificate during the next plan.
**Recommendation:** Handle certificate rotation natively in Terraform using `azurerm_key_vault_certificate` or decouple it entirely into an out-of-band automation script that doesn't conflict with IaC state.

## ~~5. Missing Azure CLI Version Pinning~~ (Fixed)
**Location:** Throughout `210-deploy-azure.yml`
**Issue:** The workflow relies on whatever `az` CLI version happens to be installed on the `ubuntu-latest` runner. This risks breaking changes if a new CLI version introduces bugs.
**Recommendation:** Use the `azure/CLI` action to pin a specific CLI version for deterministic behavior.
*(Fixed by injecting an installation step)*
