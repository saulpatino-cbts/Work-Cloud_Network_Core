# CNA Platform — Deployment Guide

> Version: 1.0.0 | Date: 2026-03-05
> Start here for first deployment.

---

## Overview

The CNA platform has two deployment surfaces:

1. **Local / operator workstation** — where `cna` CLI commands are run during an engagement
2. **GitHub Actions** — CI (every push), Release (on tag), CD Publish (manual trigger)

You do not need to deploy any server infrastructure. The platform is a CLI tool
that writes to a local `engagements/` folder and delivers to S3 or Azure Blob.

---

## Step 1 — Local Setup

```bash
git clone https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment
cd MVP-Cloud_Network_Assessment

# Install platform and dev tools
pip install -e .[dev]

# Install pre-commit hooks
pre-commit install
pre-commit run --all-files   # verify clean

# Copy and fill environment file
cp .env.example .env
# Fill in your target cloud section only (Azure OR AWS for first run)
# See documentation/secrets-reference.md for every variable
```

---

## Step 2 — Cloud Permissions

### AWS (if testing AWS)

**Discovery role** — deploy to every AWS member account:

```json
{
  "RoleName": "CNA-ReadOnly",
  "AssumeRolePolicyDocument": {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::<VENDOR_ACCOUNT_ID>:root" },
      "Action": "sts:AssumeRole"
    }]
  }
}
```

Attach AWS managed policy `ReadOnlyAccess` plus these additional actions:
`ec2:Describe*`, `directconnect:Describe*`, `organizations:List*`,
`organizations:Describe*`, `network-firewall:Describe*`, `network-firewall:List*`

Full permission list: [`cna/modules/network/module.yaml`](../cna/modules/network/module.yaml)

**Publish role** — deploy to your vendor account:

```json
{
  "RoleName": "CNA-Publish",
  "Actions": [
    "s3:PutObject", "s3:PutBucketCors",
    "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::<CNA_PUBLISH_BUCKET>",
    "arn:aws:s3:::<CNA_PUBLISH_BUCKET>/*"
  ]
}
```

**OIDC trust for GitHub Actions** (cd-publish.yml):
```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::<ACCOUNT>:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main"
    }
  }
}
```

### Azure (if testing Azure)

**Discovery permissions:**
- **Reader** role at root Management Group (inherits to all subscriptions)
- **Management Group Reader** at tenant root

```bash
# Assign Reader at root MG
az role assignment create \
  --role "Reader" \
  --assignee <CLIENT_ID_OR_OBJECT_ID> \
  --scope "/providers/Microsoft.Management/managementGroups/<TENANT_ID>"

az role assignment create \
  --role "Management Group Reader" \
  --assignee <CLIENT_ID_OR_OBJECT_ID> \
  --scope "/providers/Microsoft.Management/managementGroups/<TENANT_ID>"
```

**Publish permissions:**
- **Storage Blob Data Contributor** on the delivery storage account

```bash
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee <CLIENT_ID_OR_OBJECT_ID> \
  --scope "/subscriptions/<SUB_ID>/resourceGroups/<RG>/providers/Microsoft.Storage/storageAccounts/<ACCOUNT>"
```

**Federated identity for GitHub Actions (OIDC):**
```bash
az ad app federated-credential create \
  --id <APP_OBJECT_ID> \
  --parameters '{
    "name": "cna-github-oidc",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:saulpatinojr/MVP-Cloud_Network_Assessment:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

---

## Step 3 — GitHub Repository Secrets

Navigate to: **GitHub → Settings → Secrets and variables → Actions → New repository secret**

### AWS secrets (if using AWS delivery)

| Secret Name | Value |
|---|---|
| `CNA_AWS_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/CNA-Publish` |
| `CNA_PUBLISH_BUCKET` | Your S3 bucket name, e.g. `cna-deliverables-prod` |

### Azure secrets (if using Azure delivery)

| Secret Name | Value |
|---|---|
| `CNA_AZURE_CLIENT_ID` | App registration client ID (GUID) |
| `CNA_AZURE_TENANT_ID` | Azure AD tenant ID (GUID) |
| `CNA_AZURE_SUBSCRIPTION_ID` | Subscription ID where storage account lives |

> You only need to set secrets for the cloud you are testing first.
> CI (`ci.yml`) needs NONE of these — it runs on `GITHUB_TOKEN` alone.

---

## Step 4 — First Release

```bash
# Tag the first release — triggers release.yml
git tag v0.1.0
git push origin v0.1.0
```

This will:
1. Build the Docker image for `linux/amd64` and `linux/arm64`
2. Push to GHCR as `ghcr.io/saulpatinojr/mvp-cloud_network_assessment:0.1.0` and `:latest`
3. Create a GitHub Release with auto-generated changelog

Verify at: `https://github.com/saulpatinojr/MVP-Cloud_Network_Assessment/releases`

---

## Step 5 — First Engagement (Single Cloud)

```bash
# Set your engagement ID — format: <client>-<YYYYMMDD>-<4char>
ENGAGEMENT=testclient-20260305-a1b2

# Azure first run
cna init --client testclient --platform azure
cna discover azure --engagement-id $ENGAGEMENT --tenant-id $AZURE_TENANT_ID
cna analyze --engagement-id $ENGAGEMENT --azure
cna report preview --engagement-id $ENGAGEMENT   # inspect before signing off
cna review complete --engagement-id $ENGAGEMENT
cna report generate --engagement-id $ENGAGEMENT
cna publish run \
  --engagement-id $ENGAGEMENT \
  --cloud azure \
  --storage-account $AZURE_STORAGE_ACCOUNT_NAME \
  --container $ENGAGEMENT
cna publish status --engagement-id $ENGAGEMENT
```

---

## Step 6 — Trigger CD Publish from GitHub Actions

1. Go to **Actions → CD — Publish Portal → Run workflow**
2. Fill in:
   - `engagement_id`: e.g. `testclient-20260305-a1b2`
   - `cloud`: `aws` or `azure`
   - `image_tag`: `0.1.0` (or `latest`)
3. Click **Run workflow**

This runs `cna publish run` inside the released container using OIDC — no credentials on your machine.

---

## Pre-Go-Live Checklist

- [ ] `pip install -e .[dev]` succeeds cleanly
- [ ] `pre-commit install && pre-commit run --all-files` is clean
- [ ] CI jobs all green on `main` branch
- [ ] Cloud permissions deployed (AWS: `CNA-ReadOnly` in all accounts; Azure: Reader at root MG)
- [ ] GitHub repository secrets set for your target cloud
- [ ] `git tag v0.1.0 && git push origin v0.1.0` → release workflow green
- [ ] GHCR image visible at `ghcr.io/saulpatinojr/mvp-cloud_network_assessment`
- [ ] First engagement `cna init` → `cna discover` → `cna analyze` → `cna report` → `cna publish` completes end to end
- [ ] `cna publish status` shows portal active with TTL remaining
- [ ] Client portal URL opens in browser and deliverables download correctly
