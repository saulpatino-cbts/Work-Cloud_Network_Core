# CNA Platform — Secrets, Variables & Values Reference

> Version: 1.0.0 | Date: 2026-03-05

This document explains every secret, environment variable, and configuration value
used by the CNA platform. It covers three surfaces:
1. **Local `.env` file** — for `cna` CLI on your workstation
2. **GitHub repository secrets** — for `cd-publish.yml` workflow
3. **GitHub repository variables** — non-sensitive config (none currently required)

---

## Rule: Which Secrets Do You Actually Need?

| Scenario | Required |
|---|---|
| Run CI on every push | Nothing — `GITHUB_TOKEN` is automatic |
| Azure-only engagement (local) | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` (or `az login`) |
| AWS-only engagement (local) | `AWS_DEFAULT_REGION` + IAM credentials or `aws sso login` |
| CD Publish to Azure (GitHub Actions) | `CNA_AZURE_CLIENT_ID`, `CNA_AZURE_TENANT_ID`, `CNA_AZURE_SUBSCRIPTION_ID` |
| CD Publish to AWS (GitHub Actions) | `CNA_AWS_ROLE_ARN`, `CNA_PUBLISH_BUCKET` |
| AI enrichment (MCP) | Optional — `CNA_MCP_SERVER_URL` (default) or `AZURE_OPENAI_*` / `AWS_MCP_SERVER_URL` (cloud-specific) |
| JA regional reports | No secret — flag in CLI: `--regional-ja --ja-review-complete` |

---

## Section 1 — Local `.env` File

### Azure Discovery

| Variable | Required | Description | Example |
|---|---|---|---|
| `AZURE_TENANT_ID` | ✅ | Azure AD tenant ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `AZURE_CLIENT_ID` | ✅ | App registration or managed identity client ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `AZURE_CLIENT_SECRET` | ⚠ Optional | Only needed if using client secret auth. Leave blank for `az login` or managed identity | `your-secret-value` |

**Auth priority** (DefaultAzureCredential order):
1. Environment variables (`AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET`)
2. Workload Identity (AKS)
3. Managed Identity
4. Azure CLI (`az login`) — **simplest for local dev**
5. Azure PowerShell

For local development, just run `az login` and leave `AZURE_CLIENT_SECRET` blank.

---

### Azure Delivery Portal

| Variable | Required | Description | Example |
|---|---|---|---|
| `AZURE_STORAGE_ACCOUNT_NAME` | ✅ (Azure publish) | Storage account where portal is hosted | `cnadeliveries` |
| `AZURE_STORAGE_CONTAINER_ENGAGEMENTS` | Optional | Default container prefix | `engagements` |
| `AZURE_KEY_VAULT_URL` | Optional | Key Vault URL if secrets stored there | `https://mykeyvault.vault.azure.net/` |

---

### Azure AI / MCP (Optional)

| Variable | Required | Description |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Optional | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | Optional | Leave blank to use DefaultAzureCredential |
| `AZURE_OPENAI_DEPLOYMENT_GPT4O` | Optional | Deployment name, default `gpt-4o` |
| `AZURE_OPENAI_API_VERSION` | Optional | API version, default `2024-12-01-preview` |
| `CNA_MCP_SERVER_URL` | Optional | Default MCP server URL (fallback when cloud-specific URLs not set). Set to `none` to disable. |
| `AZURE_MCP_SERVER_URL` | Optional | Azure MCP server if self-hosted (overrides `CNA_MCP_SERVER_URL` for Azure modules) |

If none of these are set, `cna analyze` falls back to offline recommendations (DD-003). Analysis and findings are unaffected — only recommendation enrichment degrades.

---

### AWS Discovery

| Variable | Required | Description | Example |
|---|---|---|---|
| `AWS_DEFAULT_REGION` | ✅ | Home region for org API calls | `us-east-1` |
| `AWS_VENDOR_ACCOUNT_ID` | ✅ | Your management/vendor account ID | `123456789012` |
| `AWS_ACCESS_KEY_ID` | ⚠ Optional | Leave blank for SSO or instance profile | — |
| `AWS_SECRET_ACCESS_KEY` | ⚠ Optional | Leave blank for SSO or instance profile | — |
| `AWS_SESSION_TOKEN` | ⚠ Optional | Only for temporary credentials | — |

**Auth best practice for local:** Use `aws sso login` or `aws configure` with a named profile. Do not put long-lived keys in `.env`.

---

### AWS Delivery Portal

| Variable | Required | Description | Example |
|---|---|---|---|
| `CNA_PUBLISH_BUCKET` | ✅ (AWS publish) | S3 bucket name for portal delivery | `cna-deliverables-prod` |

**Bucket requirements:**
- No public access block must be disabled (portal uses pre-signed URLs, not public objects)
- CORS is configured automatically by `S3Deployer.configure_cors()` on every publish run
- Versioning: optional but recommended
- Lifecycle rule: 90-day expiry aligns with DD-019 retention policy

---

### AWS MCP (Optional)

| Variable | Required | Description |
|---|---|---|
| `AWS_MCP_SERVER_URL` | Optional | awslabs/mcp endpoint if self-hosted |

---

### Platform Config

| Variable | Required | Description | Default |
|---|---|---|---|
| `CNA_VERSION` | Optional | Platform version (informational) | `0.1.0` |
| `CNA_LOG_LEVEL` | Optional | Log verbosity | `INFO` |
| `CNA_DATA_DIR` | Optional | Where engagement folders are written | `./engagements` |

---

### Notifications (Optional)

| Variable | Required | Description |
|---|---|---|
| `TEAMS_WEBHOOK_URL` | Optional | MS Teams webhook for CRITICAL finding alerts |
| `NOTIFICATION_EMAIL_FROM` | Optional | Sender address for email notifications |

---

## Section 2 — GitHub Repository Secrets

Set at: **GitHub → Settings → Secrets and variables → Actions → Secrets**

These are only needed by `cd-publish.yml` (the CD workflow). `ci.yml` and `release.yml` use only `GITHUB_TOKEN` (automatic).

### AWS (set if publishing to S3)

| Secret Name | Description | How to Get |
|---|---|---|
| `CNA_AWS_ROLE_ARN` | Full ARN of `CNA-Publish` IAM role | `arn:aws:iam::<ACCOUNT_ID>:role/CNA-Publish` |
| `CNA_PUBLISH_BUCKET` | S3 bucket name | The bucket you created for portal delivery |

**OIDC setup required:** The `CNA-Publish` role trust policy must allow `token.actions.githubusercontent.com` as a federated principal. See `documentation/deployment-guide.md` Step 2 for the exact trust policy JSON.

### Azure (set if publishing to Azure Blob)

| Secret Name | Description | How to Get |
|---|---|---|
| `CNA_AZURE_CLIENT_ID` | App registration client ID | Azure Portal → App registrations → your app → Application (client) ID |
| `CNA_AZURE_TENANT_ID` | Azure AD tenant ID | Azure Portal → Azure Active Directory → Tenant ID |
| `CNA_AZURE_SUBSCRIPTION_ID` | Subscription where storage account lives | Azure Portal → Subscriptions |

**Federated identity required:** The app registration must have a federated credential for GitHub Actions OIDC. See `documentation/deployment-guide.md` Step 2 for the `az ad app federated-credential create` command.

### Automatic Secrets (No Setup Needed)

| Secret | Provided By | Used In |
|---|---|---|
| `GITHUB_TOKEN` | GitHub (automatic) | `ci.yml` (gitleaks SARIF upload), `release.yml` (GHCR push, GitHub Release) |

---

## Section 3 — GitHub Repository Variables

No repository variables are currently required. All configuration is either:
- In `.env` for local runs
- In repository secrets for CD
- Passed as CLI flags to `cna` commands

---

## What Is Never a Secret

These values are safe in `.env.example`, code, or CLI flags:
- `CNA_VERSION`, `CNA_LOG_LEVEL`, `CNA_DATA_DIR`
- `AWS_DEFAULT_REGION`
- `AZURE_OPENAI_DEPLOYMENT_GPT4O`, `AZURE_OPENAI_API_VERSION`
- `AZURE_STORAGE_CONTAINER_ENGAGEMENTS`
- Engagement IDs (they contain no client data themselves)

---

## Security Rules

1. **Never commit `.env`** — it is in `.gitignore` and `.dockerignore`
2. **Never put `AWS_ACCESS_KEY_ID` in a GitHub secret** — use OIDC (`CNA_AWS_ROLE_ARN`)
3. **Never put `AZURE_CLIENT_SECRET` in a GitHub secret** — use federated identity
4. **Pre-commit hooks** will block commits containing detected secrets (`detect-secrets`, `gitleaks`)
5. **CI `gitleaks-action`** scans full git history on every push — if a secret is ever accidentally committed, it will be caught and the PR will be blocked
