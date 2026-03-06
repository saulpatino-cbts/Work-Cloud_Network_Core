# CNA Platform — CI/CD Workflows Guide

> Version: 1.0.0 | Date: 2026-03-05

---

## Workflow Overview

| Workflow | File | Trigger | Needs Secrets |
|---|---|---|---|
| CI | `.github/workflows/ci.yml` | Push or PR to `main`/`develop` | None (GITHUB_TOKEN auto) |
| Release | `.github/workflows/release.yml` | `git tag v*.*.*` | None (GITHUB_TOKEN auto) |
| CD Publish | `.github/workflows/cd-publish.yml` | Manual (`workflow_dispatch`) | AWS or Azure secrets |

---

## ci.yml — Continuous Integration

**Runs on:** every push and every pull request to `main` or `develop`

**Jobs (in order):**

```
secret-scan  ─┬─ lint
              └─ (both must pass)
                      │
                 test (3.11 + 3.12 matrix)
                      │
           module-dependency-check
                      │
                 docker-build smoke test
```

| Job | What It Does | Fails If |
|---|---|---|
| `secret-scan` | gitleaks scans full git history | Any secret pattern detected |
| `lint` | ruff lint + format check | Any lint error or unformatted file |
| `test` | pytest on 3.11 AND 3.12, 80% coverage gate | Any test fails, coverage < 80% |
| `module-dependency-check` | Validates `module.yaml` dependency graph | Any missing dependency |
| `docker-build` | Builds image, runs `cna --help`, verifies non-root | Build fails, or container runs as root |

**No secrets needed.** Only `GITHUB_TOKEN` used (auto-provided).

---

## release.yml — Release

**Runs on:** `git tag v0.1.0 && git push origin v0.1.0`

**What it does:**
1. Extracts version from tag (`v0.1.0` → `0.1.0`)
2. Logs into GHCR with `GITHUB_TOKEN`
3. Builds multi-platform image (`linux/amd64` + `linux/arm64`) with layer cache
4. Pushes to GHCR:
   - `ghcr.io/saulpatinojr/mvp-cloud_network_assessment:0.1.0`
   - `ghcr.io/saulpatinojr/mvp-cloud_network_assessment:latest`
5. Creates GitHub Release with auto-generated changelog from merged PRs

**No secrets needed.** `GITHUB_TOKEN` has `packages:write` and `contents:write` in the workflow permissions block.

**To trigger:**
```bash
git tag v0.1.0
git push origin v0.1.0
```

**To re-release** (if something went wrong):
```bash
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0
git tag v0.1.0
git push origin v0.1.0
```

---

## cd-publish.yml — CD Publish Portal

**Runs on:** manual trigger only (`workflow_dispatch`)

**How to trigger:**
1. Go to **Actions → CD — Publish Portal**
2. Click **Run workflow**
3. Fill in inputs:

| Input | Required | Description | Example |
|---|---|---|---|
| `engagement_id` | ✅ | Engagement ID from `cna init` | `acme-20260305-a3f2` |
| `cloud` | ✅ | `aws` or `azure` | `azure` |
| `image_tag` | Optional | GHCR image tag to use | `0.1.0` or `latest` |

**What it does:**
1. Checks out the repo
2. Authenticates to AWS (OIDC) or Azure (federated identity) — no long-lived keys
3. Pulls the CNA container image from GHCR
4. Runs `cna publish run` inside the container
5. Outputs portal URL to workflow log

**Required secrets** (set before first use):

*AWS:*
- `CNA_AWS_ROLE_ARN`
- `CNA_PUBLISH_BUCKET`

*Azure:*
- `CNA_AZURE_CLIENT_ID`
- `CNA_AZURE_TENANT_ID`
- `CNA_AZURE_SUBSCRIPTION_ID`

**Note:** The engagement folder must exist in the repo OR be available via a mounted volume. For the CD workflow, engagement data is mounted from `github.workspace/engagements/`. For production use, you would sync the engagement folder to the runner before triggering this workflow, or adapt the workflow to pull from a shared storage location.

---

## Branch Strategy

| Branch | Purpose | Direct Commits? |
|---|---|---|
| `main` | Production — all phases signed off | No — PRs only |
| `develop` | Integration branch | No — PRs only |
| `feat/*` | Feature branches | Yes |
| `fix/*` | Bug fix branches | Yes |
| `docs/*` | Documentation-only changes | Yes |

Pre-commit hook `no-commit-to-branch` blocks direct commits to `main`.

---

## Dependabot

Automated dependency update PRs are created every **Monday at 06:00 CT** for:
- Python packages (`pyproject.toml`)
- GitHub Actions (action SHA pins)
- Docker base image (Dockerfile digest)

All Dependabot PRs require CI to pass before merge. Review the pip group PRs
(`azure-sdk`, `aws-sdk`, `testing`) weekly and merge promptly to stay current on CVEs.
