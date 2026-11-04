# Cloud Network Core — the Cloud Network Assessment (CNA) platform

[![CI](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/actions/workflows/300-test-codebase.yml/badge.svg)](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/actions/workflows/300-test-codebase.yml)
[![Release](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/actions/workflows/310-release-version.yml/badge.svg)](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/actions/workflows/310-release-version.yml)

This repository is the **internal core** of the Cloud Network Assessment platform: the single
home of the application code and of the pipeline that builds and publishes its container
images. It is not customer-facing. Customers consume one of the two **appliance** repositories —
[Azure](https://github.com/saulpatino-cbts/Work-Cloud_Network_Azure_Appliance) or [AWS](https://github.com/saulpatino-cbts/Work-Cloud_Network_AWS_Appliance) — which deploy the images published here.

A CNA-branded, multi-user web platform for cloud network assessments across AWS and Azure.
Analysts run network discoveries, AI-powered analysis, and generate presentation-ready
deliverables including an encyclopedia-grade network report. Clients receive deliverables through
a time-limited authenticated portal. The platform deploys as three containerized services behind a
managed edge, backed by PostgreSQL and authenticated via Microsoft Entra ID.

---

## Documentation map

This repository keeps exactly four required documents plus `CLAUDE.md`, and at most one
*optional* temporary working document during a release push. Everything else lives in the
[GitHub Wiki](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/wiki).

| Document | Contains |
|---|---|
| `README.md` (this file) | Repository purpose, quick start, configuration, navigation |
| [`CHANGELOG.md`](CHANGELOG.md) | Completed work, by release |
| [`REVIEW.md`](REVIEW.md) | Blockers that require a human decision, approval, or access grant |
| [`TODO.md`](TODO.md) | The engineering work queue — every actionable item, phased |
| [`CLAUDE.md`](CLAUDE.md) | Rules for AI coding agents: what this repository is (the core), the contract with the two appliance repositories, and the conventions agents get wrong |
| [`CNA-0.90-updates.md`](CNA-0.90-updates.md) | *Optional, temporary* — the one working-document exception to the four required docs: the 0.9.0 pre-demo review, cleanup record, polish plan, and the 2026-08-28 dev rebuild/deployment record (§5); retired when 0.9.0 ships |
| [GitHub Wiki](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/wiki) | Architecture, ADRs, runbooks, workflow reference, security posture, operating notes (deployment guides live with the appliances) |

If you are picking up work on this repository, start with `TODO.md`. If you are waiting on
someone, check `REVIEW.md`.

---

## Repository layout

```
apps/
├── cna-web/          Next.js web platform (8-step journey, encyclopedia, copilot)
├── cna-api/          FastAPI — metrics, chat, reports, discovery routers
└── cna-worker/       Python background worker — discovery + report generation
cna/                  Python package, installed as the `cna` CLI
├── core/             topology_schema · findings_schema · stat_masters · engagement
├── modules/          AWS + Azure discovery, FinOps signals, BC/DR signals, topology classifier
├── ai_engine/        Analysis engine, recommendation engine, chat agent
├── report_engine/    Encyclopedia renderer, WeasyPrint PDF, radar chart SVG
├── diagram_engine/   Draw.io generator, future-state model
├── delivery_portal/  Client deliverable delivery
└── cli/              Command-line entry point
scripts/              Repository guards (documentation model, module graph, shape catalog)
                      and the headless draw.io wrapper the images use
tests/                unit/ and integration/
.github/workflows/    200 build images · 300 test · 310 release · 370 registry cleanup · 390 scan images
.deployment-catalog/  latest-build.json — the build manifest the appliances consume
.claude/ .agents/ .codex/ .kiro/   Vendored agent configuration — not project source
```

---

## Repository topology

CNA is delivered as one internal **core** repository (this one) and two customer-facing
**appliance** repositories, one per cloud:

| Repository | Owns | Does not contain |
|---|---|---|
| `Work-Cloud_Network_Core` (core, this repository) | Application code (`apps/`, `cna/`), container image builds and publishing (`200-build-images.yml`), tests and releases | Customer deployments |
| [`Work-Cloud_Network_Azure_Appliance`](https://github.com/saulpatino-cbts/Work-Cloud_Network_Azure_Appliance) | Azure Terraform, deploy / update / drift / teardown workflows, the Azure release catalog | Application code, anything AWS |
| [`Work-Cloud_Network_AWS_Appliance`](https://github.com/saulpatino-cbts/Work-Cloud_Network_AWS_Appliance) | AWS Terraform, the same workflows, the AWS release catalog | Application code, anything Azure |

The two appliances are structurally identical — same file names, workflow numbers, inputs,
catalog schema, scripts, and documents — differing only in the cloud-specific parts each README
enumerates. **Features ship once, here, in the images.** When `200-build-images.yml` publishes a
new image set it commits `.deployment-catalog/latest-build.json` and sends a `repository_dispatch`
(`cna-image-published`) to every repository named in the `APPLIANCE_REPOS` variable; each
appliance also polls the manifest. An appliance auto-deploys new images to `dev` and opens an
"update available" issue for `prod`, which a human approves through its deploy workflow's
approval gate. The full contract is in [`CLAUDE.md`](CLAUDE.md).

The project started as a single repository, `Work-Cloud_Network_Assessment`, which held the core
until 2026-09-18. Its full history is imported here (`TODO.md` → T-509), so commit references in
`CHANGELOG.md` still resolve; the original repository is retired and being deleted (`REVIEW.md`
→ R-014), so its issue and pull-request numbers in the documents are historical references only.
New work, issues and pull requests belong here.

Every deploy is run from the appliance's **Run workflow** dialog, where `ai_mode` selects the AI
provider family: `saas` (Azure OpenAI on Azure, Amazon Bedrock on AWS — provisioned by
Terraform, authenticated with the workload identity) or `byo-api` (no cloud AI resources; an
admin pastes an Anthropic and/or OpenAI API key on the **AI Engine** admin page — the only
secrets ever entered in the app, stored encrypted in the database).

---

## Quick start

### Web platform, locally

```bash
cd apps/cna-web
cp .env.example .env.local
# Fill in DATABASE_URL, NEXTAUTH_SECRET, AZURE_AD_* values
npm install
npm run db:migrate
npm run dev          # http://localhost:3000
```

Other useful scripts: `npm run build`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run db:studio`, `npm run db:generate` — the first three plus `npm test` are what `300 · Test Codebase` runs for the web tier.

### Python CLI, locally

Requires Python 3.11 or newer.

```bash
pip install -e .[dev]
pre-commit install
cp .env.example .env
cna --help
```

Lint and test the Python package with `ruff check cna/`, `ruff format --check`, and `pytest`.

The container images do not resolve dependencies at build time: they install the resolution
committed in `uv.lock` with hash checking. After changing a dependency in `pyproject.toml`, run
`uv lock` (uv ≥ 0.12.21) and commit the updated lock alongside it — CI fails when the two disagree.

### Client installation and deployment

This repository is the internal image source, **not** the customer installer. Do not deploy the
core repository or run Terraform from it. Install from exactly one customer-facing appliance:
choose Azure or AWS, then follow that appliance repository's **README → Operating the appliance**
and its `REVIEW.md` / `TODO.md` prerequisites:
[Azure appliance](https://github.com/saulpatino-cbts/Work-Cloud_Network_Azure_Appliance) ·
[AWS appliance](https://github.com/saulpatino-cbts/Work-Cloud_Network_AWS_Appliance).

Use this sequence before a client deployment:

1. Select the client's cloud and GitHub organization, and review the chosen appliance's supported
   regions, prerequisites, required roles, state-backend setup, workflow inputs, and approval
   gates. Resolve its open review blockers with the client account owners; do not copy deployment
   steps from this core repository.
2. Fill in the appliance's documented non-secret placeholders for the client-owned repository,
   cloud account or subscription, region, state backend, domain, and image-pull identity. Treat
   ``<client-owner>``, ``<client-repository>``, and
   ``<cloud-account-or-subscription>`` as prompts to replace in the appliance's own settings.
   Do the same for ``<region>`` and ``<state-backend>``; these are not literal values or values to
   add to this core repository.
3. Configure the appliance repository's GitHub variables, OIDC trust, and cloud secret manager
   exactly as its setup guide specifies. Keep credentials and key material in the approved secret
   store; never put them in a workflow input, command line, committed file, or unapproved `.env`
   file or artifact. Terraform state and saved plans can contain secret values even when inputs
   are marked sensitive; keep them in the client's access-controlled backend and never publish
   them as installation evidence. The core's `.env.example` is a runtime inventory and
   local-development template, not a production deployment file.
4. Choose `saas` or `byo-api` only after reviewing the appliance and security decisions. `saas`
   uses the appliance cloud's managed identity. BYO-AI keys are entered only in the application's
   authorized AI Engine administration UI; do not inject provider keys through environment
   variables, Terraform, or workflow inputs. **BYO-AI remains subject to the open security and
   product-owner decisions in `REVIEW.md` R-011 and R-021.** The current single-key encryption
   configuration cannot be rotated without coordinated keyring/re-encryption work (`TODO.md`
   T-707); preserve the configured key and an approved recovery procedure.
5. Run the appliance's documented bootstrap and deployment workflow for its non-production
   environment first. Review its health checks and deployment evidence, then use its production
   approval gate and change/rollback procedure. The appliance is the authority for exact commands,
   inputs, resource names, cloud roles, and recovery steps.
6. Confirm the deployed image tag and digest and review current signature/provenance and scan
   evidence before promoting according to the client's release policy. Core workflow
   `390-scan-images` scans after publication; it is **detection, not a pre-deployment gate**.
   A signature or catalog entry alone does not mean an image is vulnerability-free. If fresh scan
   evidence is unavailable, treat scan status as unknown and resolve that through the client's
   release owner before production use.

#### Client identities, provider selection, and credential lifecycle

Each appliance is a **single-client security boundary**. Give each client its own database,
storage, secret manager, encryption key, authentication registration, and runtime identities.
BYO provider settings are appliance-wide `AppSetting` rows, not per-engagement keys. Engagement
membership does not make a shared appliance safe for unrelated customers.

Keep the identities separate:

| Identity or setting | Ownership and use |
|---|---|
| Client bootstrap identity | Creates the client's backend and initial trust; not the app runtime identity. |
| Client deploy OIDC identity | Limited to the client's repository, approved environment, and deployment resources; never copy another client's trust subjects. |
| App runtime identity | Only the secret, storage, database, and cloud-AI access the running services need; not deployment or secret-administration access. |
| Upstream publisher | The chosen image producer. Its repository, workflow OIDC signing identity, issuer, and provenance builder must match the verified catalog. A client fork does not make the deploy owner the upstream signer. |
| `CORE_OWNER` / `CORE_REPO` | Appliance-side upstream source settings, not tenant/account IDs or credentials. Follow each appliance's current input names and explicitly select the real publisher. |
| `LOCAL_ADMIN_PASSWORD` | Optional break-glass **PBKDF2 hash**, never a plaintext password. Leave it unset to disable that path; provide it only through the appliance's protected secret procedure. |

**Prepared contract, not yet deployed:** the matching Core release for `byo-api` requires
`CNA_BYO_AI_PROVIDERS`: an explicit nonempty JSON
array containing only the client-approved `anthropic` and/or `openai` identifiers, with no
duplicates. Both the web and API service must receive the same list. Missing, malformed,
placeholder, or incompatible provider/default settings fail closed rather than authorizing all
providers. Set `CNA_AI_ENGINE_DEFAULT` to one of the selected providers. These are non-secret
configuration values; provider API keys remain UI-only. Both appliances must adopt this contract
with the matching Core release before enabling BYO-AI.

Provider selection is **not a network egress firewall**. Saving a key probes the selected
provider's models endpoint; analysis/chat can send findings, topology, documents, and prompts to
that provider. Obtain the client's data-processing, retention, residency, and outbound-network
approval first (R-011/R-021). Configure and verify the appliance's network policy separately;
do not infer blocked internet access from an app allowlist or private inbound connectivity.

Only an authenticated platform ADMIN may save or remove BYO keys. Keys are encrypted with
AES-256-GCM in the client's database and decrypted server-side for provider requests; the UI
shows only a hint. Do not copy keys or raw SDK/HTTP errors into screenshots, logs, support
bundles, workflow outputs, or plan artifacts. Review any exported evidence for secrets first.
Removing a key deletes its stored key and hint, but keeps its model override and does not revoke
the provider credential, cancel in-flight calls, or erase database backups. Provider revocation
and backup retention remain client-owned operations.

Replacing a provider API key and rotating `CREDENTIAL_ENCRYPTION_KEY` are different operations.
For a provider-key replacement, use the authorized admin UI and the client's approved provider
revocation procedure; never paste credentials into deployment inputs. **Do not replace the
encryption key in place:** existing ciphertext has no key ID and will become unreadable.
T-707's coordinated keyring/re-encryption migration is still outstanding. Preserve the existing
key in the client's recovery vault and restore a matching database/key pair when recovering.
Verify recovery in an isolated client-owned non-production environment without exposing secrets.

For installation verification, confirm health/readiness, authentication and authorization,
the running immutable image digests, signer/provenance checks, scan date/policy, and an approved
non-production workflow. For rollback, use the appliance's reviewed release catalog and migration
compatibility procedure; do not blindly roll database state or encryption keys backward. Cleanup
must follow the client's retention and revocation policy for provider credentials, runtime
secrets, backups, storage, state, and artifacts. No cleanup or rotation is automatic here.

Deployment does not happen from this repository. Each appliance repository owns its cloud's
Terraform, bootstrap, deploy, drift and teardown workflows and documents the procedure in its
`README.md` → *Operating the appliance*: [Azure](https://github.com/saulpatino-cbts/Work-Cloud_Network_Azure_Appliance) · [AWS](https://github.com/saulpatino-cbts/Work-Cloud_Network_AWS_Appliance). This repository
only publishes the images they deploy (`200-build-images.yml`). Deployment blockers live in the
appliances' `REVIEW.md` files; the AWS appliance's deploy stays fail-fast until its account,
state backend and OIDC role exist (its R-001 – R-003).

---

## Configuration

Configuration comes from three places, in this order of authority:

1. **GitHub Secrets and Variables** — for this repository, only what the build and release
   workflows need (Docker Hub, the GitHub App for appliance notification). Deployment secrets and
   variables belong to the appliance repositories, where cloud credentials use OIDC and there are
   no long-lived keys.
2. **The appliance's vault** (Azure Key Vault / AWS Secrets Manager) — runtime secrets for a
   deployed environment, injected by the appliance's Terraform; its `340-sync-keys` workflow can
   pull them into a short-lived `.env` artifact.
3. **`.env` / `.env.local`** — local development only, never committed.

`.env.example` at the repository root documents the runtime environment contract and which
side (appliance Terraform or local `.env`) supplies each listed value. Inventory drift remains
tracked by `TODO.md` T-711; do not assume these templates enumerate every runtime variable.
`apps/cna-web/.env.example` documents web-specific values. The Wiki's **Secrets
Reference** explains each value in full.

### Web file storage (Core #70 / CR-CORE-01)

The web tier selects its backend using `CNA_APPLIANCE_CLOUD`. On AWS it uses the
appliance-injected `CNA_STORAGE_BUCKET` (a bucket name, not a URL) and AWS SDK v3's
default workload credential and region chains. It does not need Azure storage
configuration, static keys, or a custom endpoint. On Azure it retains
`AZURE_STORAGE_ACCOUNT_NAME` and optional `AZURE_STORAGE_CONTAINER_ENGAGEMENTS`
(default `raw-artifacts`).

Documents and diagrams use `raw-artifacts/<engagementId>/<file>` on S3;
deliverables use `deliverables/<engagementId>/<file>`. Azure retains its configured
engagement container and the `deliverables` container. Stored paths are relative
keys, never external URLs. Download/delete operations require the authorized
engagement ID; read-only download links expire within one hour and their redirects
are not cached. Portal cleanup targets only `portal-<engagementId>/` on S3 (never
the bucket), or that engagement's Azure container. Cleanup removes current objects;
version retention, soft deletion and lifecycle remain appliance policy.

Upload, diagram and assessment controls become available when the selected storage
configuration is valid. **External client portal publishing remains Azure-only**:
the Python API's `POST /publish` still uses `AzureBlobDeployer`; its AWS conversion
is a separate T-709 follow-up. Both appliances must verify their runtime identities
and configuration before adopting the image: AWS needs bucket-scoped
`s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` and prefix-scoped `s3:ListBucket`;
Azure retains Blob data access and user-delegation signing permissions. No IAM,
storage policy, deployment, or live-cloud verification is performed by this local change.

---

## Repository conventions

- **Four documents plus `CLAUDE.md`, one wiki.** `README.md`, `CHANGELOG.md`, `REVIEW.md`,
  `TODO.md`, and `CLAUDE.md` (agent instructions) are the only markdown files in the repository.
  Long-form documentation goes to the Wiki. Content determines destination, not filename.
- **The appliance contract is mirrored, never implied.** Any change to the image tag scheme, the
  build manifest, the `cna-image-published` dispatch, or the runtime environment contract
  (`CNA_AI_MODE`, `CNA_APPLIANCE_CLOUD`, …) is made in both appliance repositories in the same
  change set — see [`CLAUDE.md`](CLAUDE.md).
- **Numbered workflows.** Workflows use numeric bands shared by the core and both appliances:
  `000` bootstrap, `100` validation, `200` build and deploy, `300` test, release, and operations.
  The core keeps `200`, `300`, `310` and `370`; the appliances keep the rest. Within a band, the
  number is stable — reference workflows by filename, not by position, and never renumber.
- **Never hardcode a value at a call site.** Regions, endpoints, account IDs, and every other
  environment-specific value is *declared* — as a `DiscoveryOptions` field, a named module-level
  constant, or a setting — and resolved at runtime, most specific source first. That is the point
  of the declared lists: they record what to use later, and they can be overridden. A declared
  default is a last resort, never an inline literal.
- **All GitHub Actions are pinned to a SHA digest.** `detect-secrets` runs at commit time and in
  CI, and **fails the build** on any finding not recorded in `.secrets.baseline` — which holds only
  hand-audited false positives, never a suppression dump. `gitleaks` also runs in CI but is
  advisory: it needs a paid licence on private repositories, so its job is `continue-on-error` and
  cannot fail a build. Do not read it as a gate.
- **Vendored agent configuration** under `.claude/`, `.agents/`, `.codex/`, and `.kiro/` is configuration,
  not project source. It is excluded from lint (see `pyproject.toml`) and from the documentation
  model, and it must never contain project-specific facts.

---

*Maintained by CBTS.*
