# CLAUDE.md — Cloud Network Core

Instructions for AI coding agents working in this repository. `README.md` is the
human intro page; this file states the rules an agent must not infer wrongly.

## What this repository is

This is the **core** of the Cloud Network Assessment (CNA) platform: the single
source of application code — `apps/cna-web`, `apps/cna-api`, `apps/cna-worker`,
and the `cna` Python package — and the pipeline that builds and publishes their
container images (`200-build-images.yml` → Docker Hub `<namespace>/cna`).

It is **internal, never customer-facing**: customers consume an appliance, not this
repository. The project's original repository, `Work-Cloud_Network_Assessment`, held this
code until 2026-09-18; its history is imported here and it is archived. Never open work
there — every reference to it that remains in the documents is a historical link to an
issue or pull request that lives in the archive.

Deployment is not this repository's job. Each cloud has its own customer-facing
**appliance repository** that deploys and operates these images:

- Azure: <https://github.com/saulpatinojr/Work-Cloud_Network_Azure_Appliance>
- AWS: <https://github.com/saulpatinojr/Work-Cloud_Network_AWS_Appliance>

The appliances contain only their cloud's Terraform and deploy/update workflows.
They are structurally identical to each other; a feature lands **once, here**, in
the images, and both appliances pick it up. There is no Terraform and no deploy
workflow in this repository; the core keeps only `200-build-images`,
`300-test-codebase`, `310-release-version` and `370-registry-cleanup`. A
deployment fix belongs in the appliance (and its sibling), never here.

## The core ↔ appliance contract

Changing any of the following changes both appliances. Mirror the change into
**both** appliance repositories in the same change set (link the sibling PRs),
or record a `TODO.md` item naming them — never leave one side implied.

1. **Image tag scheme** on Docker Hub: `cna:{api,worker,web,migrator}-sha-<7>`
   immutable tags plus floating `*-latest`; the CLI image is `cna:sha-<7>` /
   `cna:latest`.
2. **`.deployment-catalog/latest-build.json`** — fields `sha_tag`, `commit`,
   `built_at`, `run_id`, `images{cli,api,worker,web,migrator}` (immutable tags)
   and `digests{cli,api,worker,web,migrator}` (`docker.io/<ns>/cna@sha256:<64>`).
   Written and committed by `200-build-images.yml` after every image passed the
   vulnerability gate; read by the appliances' image-update workflow, which
   deploys the combined form `docker.io/<ns>/cna:<role>-sha-<7>@sha256:<64>` —
   tag for people and for the web tier's image-update check, digest as the
   authoritative pull. Floating `*-latest` tags are never deployed.
3. **`repository_dispatch` event `cna-image-published`** with the manifest as
   `client_payload`, sent by `200-build-images.yml` to every repository listed in
   the `APPLIANCE_REPOS` variable (comma-separated names under this owner). It is
   a fast path only — the appliances also poll the manifest, so a failed dispatch
   is a warning, never a failed build.
4. **Runtime environment contract** the images read, injected by the appliances'
   Terraform: `CNA_AI_MODE` (`saas` | `byo-api`), `CNA_APPLIANCE_CLOUD`
   (`azure` | `aws`), `CNA_AI_ENGINE_DEFAULT`, the SaaS engine variables
   (`AZURE_OPENAI_*` on Azure, `CNA_BEDROCK_*` on AWS), and
   `CREDENTIAL_ENCRYPTION_KEY` (web always; api in `byo-api`), and the image-update
   check inputs the web tier reads (`CNA_WEB_IMAGE`, `CNA_IMAGE_REGISTRY_USERNAME`,
   `CNA_IMAGE_REGISTRY_TOKEN`, `CNA_APPLIANCE_REPO`, optional
   `CNA_IMAGE_UPDATE_CHECK_INTERVAL_MINUTES`). `CNA_BUILD_SHA` is baked into every
   image by `200-build-images.yml`, never injected. The authoritative inventory is
   `.env.example`.

## AI engine rules

- Engine ids are `azure-openai`, `bedrock`, `anthropic`, `openai`. The selection
  rules live in `apps/cna-web/lib/ai-engine-rules.ts` and
  `cna/ai_engine/chat_agent.py` and are pinned by **one shared vector table**
  (`ai-engine-rules.test.ts`, `tests/unit/test_chat_agent.py`). Change both
  files and both tests together.
- `saas` mode uses the cloud-native engine for the appliance's cloud. `byo-api`
  mode uses admin-entered Anthropic/OpenAI keys. Those keys are the **only**
  secrets entered in the app UI; they are AES-256-GCM encrypted
  (`apps/cna-web/lib/crypto.ts` ↔ `cna/core/credential_crypto.py`, kept
  byte-compatible by a Node-generated test vector) and stored as `AppSetting`
  rows `ai.byo.<provider>.{apiKey,keyHint,model}`. Never log, return, or
  persist a decrypted key anywhere else; never accept one through env,
  Terraform, or a workflow input.
- Model ids are settings/variables with code defaults, never inline literals at
  call sites. Verify current ids before changing a default.

## Repository conventions that agents get wrong

- **Documents:** `README.md`, `CHANGELOG.md`, `REVIEW.md`, `TODO.md`, and this
  `CLAUDE.md` are the only markdown files (plus at most one temporary
  release-push document). `scripts/validate_documentation_model.py` enforces
  this in CI. Long-form docs go to the GitHub Wiki. Content determines
  destination, not filename.
- **Never hardcode a value at a call site.** Declare it (`DiscoveryOptions`
  field, module-level constant, setting) and resolve at runtime.
- **Workflows are numbered in bands** (`000` bootstrap, `100` validation, `200`
  build/deploy, `300` test/release/ops). Numbers are stable across core and
  both appliances; never renumber, reference by filename. The core owns `200`,
  `300`, `310`, `370`; every other number belongs to the appliances.
- **Every GitHub Action is pinned to a SHA digest.** `detect-secrets` fails the
  build on any finding not in `.secrets.baseline`; `gitleaks` is advisory.
- **Secrets** travel as GitHub secrets → OIDC / Key Vault / Secrets Manager →
  container secrets (injected by the appliances' Terraform). Never on a command
  line, never in a `workflow_dispatch` input, never committed.
- **Vendored agent configuration** under `.claude/`, `.agents/`, `.codex/`, `.kiro/` is
  not project source and must never contain project-specific facts.
- Start with `TODO.md` when picking up work; check `REVIEW.md` when blocked on a
  human decision.
