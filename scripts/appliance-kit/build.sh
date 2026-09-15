#!/usr/bin/env bash
# Assemble one appliance repository tree from this core checkout.
#   scripts/appliance-kit/build.sh azure|aws
# Output: $OUT_ROOT/<cloud>/ (default /tmp/cna-appliances/<cloud>) — a fresh
# clone of the appliance repository on branch claude/appliance-bootstrap with
# the tree staged; review, commit and push it from there. Needs git, python3,
# and detect-secrets (pip install detect-secrets) on PATH or in .venv/.
# Templates end in .tmpl so the documentation-model guard ignores them; the
# suffix is stripped on render.
set -euo pipefail

CLOUD="${1:?azure|aws}"
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE="${CORE:-$(cd "$KIT/../.." && pwd)}"
OUT_ROOT="${OUT_ROOT:-${TMPDIR:-/tmp}/cna-appliances}"
PY="${PY:-$([ -x "$CORE/.venv/bin/python" ] && echo "$CORE/.venv/bin/python" || command -v python3)}"
DS="${DS:-$([ -x "$CORE/.venv/bin/detect-secrets" ] && echo "$CORE/.venv/bin/detect-secrets" || command -v detect-secrets)}"
BRANCH="claude/appliance-bootstrap"
DATE="$(date -u +%Y-%m-%d)"
CORE_COMMIT="$(git -C "$CORE" rev-parse --short HEAD)"

case "$CLOUD" in
  azure) REPO=Work-Cloud_Network_Azure_Appliance; SIBLING_REPO=Work-Cloud_Network_AWS_Appliance; OTHER=aws ;;
  aws)   REPO=Work-Cloud_Network_AWS_Appliance;   SIBLING_REPO=Work-Cloud_Network_Azure_Appliance; OTHER=azure ;;
  *) echo "unknown cloud $CLOUD" >&2; exit 2 ;;
esac

OUT="$OUT_ROOT/$CLOUD"
rm -rf "$OUT"; mkdir -p "$OUT_ROOT"
git clone -q "https://github.com/saulpatinojr/$REPO.git" "$OUT"
git -C "$OUT" checkout -q -b "$BRANCH"

cd "$OUT"
mkdir -p .github/workflows .github/ISSUE_TEMPLATE infra/terraform/modules infra/terraform/environments \
         scripts/ci .deployment-catalog/dev .deployment-catalog/prod

# ── Terraform: providers/<cloud>/* -> modules/*, environments/<cloud>/* -> environments/* ──
cp -r "$CORE/infra/terraform/providers/$CLOUD/." infra/terraform/modules/
cp -r "$CORE/infra/terraform/environments/$CLOUD/dev"  infra/terraform/environments/dev
cp -r "$CORE/infra/terraform/environments/$CLOUD/prod" infra/terraform/environments/prod
find infra/terraform -name '.terraform' -type d -prune -exec rm -rf {} + 2>/dev/null || true
"$PY" - "$CLOUD" <<'EOF'
import pathlib, sys
cloud = sys.argv[1]
old = f"../../../../providers/{cloud}/"
n = 0
for tf in pathlib.Path("infra/terraform/environments").rglob("*.tf"):
    s = tf.read_text()
    if old in s:
        tf.write_text(s.replace(old, "../../../modules/")); n += 1
print(f"rewrote module sources in {n} files")
EOF

# ── Workflows ──────────────────────────────────────────────────────────────────
WF="$CORE/.github/workflows"
cp "$KIT/common/.github/workflows/230-image-update.yml" .github/workflows/
cp "$KIT/common/.github/workflows/300-validate.yml" .github/workflows/
cp "$KIT/common/.github/ISSUE_TEMPLATE/update-available.md.tmpl" .github/ISSUE_TEMPLATE/update-available.md

if [ "$CLOUD" = azure ]; then
  for f in 000-bootstrap-backend 100-validate-prereqs 220-fast-redeploy 330-teardown 340-sync-keys 350-drift-dev 360-drift-prod; do
    cp "$WF/$f.yml" .github/workflows/
  done
  cp "$WF/211-deploy-azure-split.yml" .github/workflows/210-deploy.yml
  cp "$CORE/scripts/"*.ps1 scripts/
else
  for f in 000-bootstrap-backend 100-validate-prereqs 220-fast-redeploy 330-teardown 340-sync-keys 350-drift-dev 360-drift-prod; do
    "$PY" - "$KIT/aws/$f.yml" "$KIT/aws/scaffold-header.txt" ".github/workflows/$f.yml" <<'EOF'
import pathlib, sys
src, hdr, dst = (pathlib.Path(p) for p in sys.argv[1:4])
dst.write_text(src.read_text().replace("@@SCAFFOLD_HEADER@@\n", hdr.read_text()))
EOF
  done
  cp "$WF/212-deploy-aws-split.yml" .github/workflows/210-deploy.yml
fi
cp "$WF/320-publish-portal.yml" .github/workflows/320-publish-portal.yml

"$PY" - "$CLOUD" "$OTHER" <<'EOF'
import pathlib, re, sys
cloud, other = sys.argv[1:3]
wfdir = pathlib.Path(".github/workflows")

def sub(path, pairs, required=True):
    p = wfdir / path; s = p.read_text()
    for old, new in pairs:
        if required and old not in s:
            raise SystemExit(f"{path}: expected snippet not found:\n{old}")
        s = s.replace(old, new)
    p.write_text(s)

# Path layout: environments/<cloud>/ -> environments/ ; providers/<cloud> -> modules
for p in wfdir.glob("*.yml"):
    s = p.read_text()
    s = s.replace(f"infra/terraform/environments/{cloud}/", "infra/terraform/environments/")
    s = s.replace(f"infra/terraform/providers/{cloud}/", "infra/terraform/modules/")
    s = s.replace(f"providers/{cloud}/", "modules/")
    p.write_text(s)

# 210-deploy: one name, one concurrency group, one self-reference across both appliances.
if cloud == "azure":
    sub("210-deploy.yml", [
        ('name: "211 · Deploy Azure Platform (Split)"', 'name: "210 · Deploy"'),
        ("group: deploy-azure-platform-", "group: deploy-"),
    ])
    # Workflow names are shared across both appliances.
    sub("330-teardown.yml", [('name: "330 · Teardown Azure Platform"', 'name: "330 · Teardown Platform"')])
    s = (wfdir / "210-deploy.yml").read_text().replace("211-deploy-azure-split", "210-deploy")
    (wfdir / "210-deploy.yml").write_text(s)
else:
    sub("210-deploy.yml", [
        ('name: "212 · Deploy AWS Platform (Split)"', 'name: "210 · Deploy"'),
        ("group: deploy-aws-platform-", "group: deploy-"),
    ])
    s = (wfdir / "210-deploy.yml").read_text()
    s = s.replace("212-deploy-aws-split.yml", "210-deploy.yml").replace("211-deploy-azure-split.yml", "the Azure appliance's 210-deploy.yml")
    s = s.replace("https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110", "the core repository's REVIEW.md R-001 – R-003")
    (wfdir / "210-deploy.yml").write_text(s)

# 320-publish-portal: this appliance publishes to its own cloud's storage only.
p = wfdir / "320-publish-portal.yml"; s = p.read_text()
cloud_input = """      cloud:
        description: 'Cloud storage target'
        required: true
        type: choice
        options: [aws, azure]
        default: aws
"""
assert cloud_input in s, "320: cloud input block not found"
s = s.replace(cloud_input, "")
s = s.replace("# Triggered manually (workflow_dispatch) or on a workflow_call from another pipeline.",
              "# Triggered manually (workflow_dispatch).")
aws_step = """      # AWS OIDC — no long-lived keys
      - name: Configure AWS credentials (OIDC)
        if: inputs.cloud == 'aws'
"""
azure_step = """      # Azure OIDC — uses same AZURE_* secrets as all other workflows
      - name: Configure Azure credentials (OIDC)
        if: inputs.cloud == 'azure'
"""
assert aws_step in s and azure_step in s, "320: OIDC steps not found"
if cloud == "azure":
    # drop the AWS block entirely (from its comment to the Azure comment)
    start = s.index(aws_step); end = s.index(azure_step)
    s = s[:start] + s[end:]
    s = s.replace(azure_step, azure_step.replace("        if: inputs.cloud == 'azure'\n", ""))
    s = s.replace("          CLOUD: ${{ inputs.cloud }}\n", "          CLOUD: azure\n")
    s = s.replace("""      - name: Validate publish inputs
        env:
          CLOUD: azure
          STORAGE_ACCOUNT: ${{ inputs.azure_storage_account }}""",
    """      - name: Validate publish inputs
        env:
          CLOUD: azure
          STORAGE_ACCOUNT: ${{ inputs.azure_storage_account }}""")
    s = s.replace("""          if [ "$CLOUD" = "azure" ] && [ -z "$STORAGE_ACCOUNT" ]; then
            echo "::error::azure_storage_account is required when cloud=azure."
            exit 1
          fi""", """          if [ -z "$STORAGE_ACCOUNT" ]; then
            echo "::error::azure_storage_account is required."
            exit 1
          fi""")
    s = s.replace("        description: 'Azure Blob storage account name (required when cloud=azure)'\n        required: false",
                  "        description: 'Azure Blob storage account name'\n        required: true")
    s = s.replace("        description: 'Azure Blob container name (defaults to engagement_id when cloud=azure)'",
                  "        description: 'Azure Blob container name (defaults to engagement_id)'")
    s = s.replace("""          if [ "$CLOUD" = "aws" ]; then
            ARGS+=(--bucket "$PUBLISH_BUCKET")
          else
            ARGS+=(--storage-account "$AZURE_STORAGE_ACCOUNT")
            if [ -n "$AZURE_CONTAINER" ]; then
              ARGS+=(--container "$AZURE_CONTAINER")
            fi
          fi""", """          ARGS+=(--storage-account "$AZURE_STORAGE_ACCOUNT")
          if [ -n "$AZURE_CONTAINER" ]; then
            ARGS+=(--container "$AZURE_CONTAINER")
          fi""")
    s = s.replace("          PUBLISH_BUCKET: ${{ secrets.CNA_PUBLISH_BUCKET }}\n", "")
    s = s.replace("            -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \\\n", "")
    s = s.replace("#   CNA_AWS_ROLE_ARN     — IAM role ARN for CNA-Publish (OIDC)\n#   CNA_PUBLISH_BUCKET   — S3 bucket name\n", "")
    s = s.replace("#   - Uses OIDC (no long-lived AWS keys stored as secrets)", "#   - Uses OIDC (no long-lived keys stored as secrets)")
else:
    start = s.index(azure_step)
    end = s.index("      - name: Log in to Docker Hub")
    s = s[:start] + s[end:]
    s = s.replace(aws_step, aws_step.replace("        if: inputs.cloud == 'aws'\n", ""))
    s = s.replace("          CLOUD: ${{ inputs.cloud }}\n", "          CLOUD: aws\n")
    s = s.replace("          STORAGE_ACCOUNT: ${{ inputs.azure_storage_account }}\n", "")
    s = s.replace("""          if [ "$CLOUD" = "azure" ] && [ -z "$STORAGE_ACCOUNT" ]; then
            echo "::error::azure_storage_account is required when cloud=azure."
            exit 1
          fi
""", "")
    for blk in ("""      azure_storage_account:
        description: 'Azure Blob storage account name (required when cloud=azure)'
        required: false
        default: ''
        type: string
""", """      azure_container:
        description: 'Azure Blob container name (defaults to engagement_id when cloud=azure)'
        required: false
        default: ''
        type: string
"""):
        assert blk in s, "320: azure input block not found"
        s = s.replace(blk, "")
    s = s.replace("""          if [ "$CLOUD" = "aws" ]; then
            ARGS+=(--bucket "$PUBLISH_BUCKET")
          else
            ARGS+=(--storage-account "$AZURE_STORAGE_ACCOUNT")
            if [ -n "$AZURE_CONTAINER" ]; then
              ARGS+=(--container "$AZURE_CONTAINER")
            fi
          fi""", """          ARGS+=(--bucket "$PUBLISH_BUCKET")""")
    s = s.replace("          AZURE_STORAGE_ACCOUNT: ${{ inputs.azure_storage_account }}\n          AZURE_CONTAINER: ${{ inputs.azure_container }}\n", "")
    s = s.replace("            -e AZURE_CLIENT_ID -e AZURE_TENANT_ID -e AZURE_SUBSCRIPTION_ID \\\n", "")
    s = s.replace("#   AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_SUBSCRIPTION_ID — same as all other workflows\n", "")
assert "inputs.cloud" not in s, "320: a cloud reference survived"
p.write_text(s)
print("workflows rewritten")
EOF

# ── Scripts, catalog, hygiene files ───────────────────────────────────────────
cp -r "$CORE/scripts/ci/." scripts/ci/
cp "$CORE/scripts/bootstrap-runner.sh" "$CORE/scripts/validate_documentation_model.py" scripts/
if [ "$CLOUD" = azure ]; then
  cp "$CORE/.deployment-catalog/dev/"*.json .deployment-catalog/dev/
else
  touch .deployment-catalog/dev/.gitkeep
fi
touch .deployment-catalog/prod/.gitkeep
cp "$CORE/.gitignore" .gitignore
"$PY" - "$CORE/.pre-commit-config.yaml" <<'EOF'
import pathlib, sys
s = pathlib.Path(sys.argv[1]).read_text()
# No pyproject here: drop the local `ty` hook block, keep everything else identical.
i = s.index("  # --- Type checking (TODO.md T-402) ---")
pathlib.Path(".pre-commit-config.yaml").write_text(s[:i].rstrip() + "\n")
EOF

# ── Documents from templates ──────────────────────────────────────────────────
"$PY" - "$KIT" "$CLOUD" "$REPO" "$SIBLING_REPO" "$DATE" "$CORE_COMMIT" <<'EOF'
import pathlib, sys
kit, cloud, repo, sibling, date, core_commit = sys.argv[1:7]
T = pathlib.Path(kit) / "templates"

spec = {
  "azure": dict(
    CLOUD_TITLE="Azure", SIBLING_TITLE="AWS",
    COMPUTE="Container Apps, PostgreSQL Flexible Server, Key Vault, Front Door + WAF, Azure Firewall, AI Foundry",
    SIBLING_COMPUTE="ECS Fargate + ALB, RDS PostgreSQL, Secrets Manager, CloudFront + WAF, Bedrock",
    STATE_BACKEND="`azurerm`: storage account + container (`location`, `region_short`, `tfstate_resource_group`, `tfstate_storage_account`, `tfstate_container`)",
    SIBLING_STATE_BACKEND="`s3` + DynamoDB lock table (`region`, `region_short`, `tfstate_bucket`, `tfstate_lock_table`)",
    OIDC_SECRETS="`azure/login` — `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`",
    SIBLING_OIDC_SECRETS="`aws-actions/configure-aws-credentials` — `AWS_DEPLOY_ROLE_ARN`",
    VAULT="Azure Key Vault", SIBLING_VAULT="AWS Secrets Manager",
    FAST_REDEPLOY="`az containerapp update`", SIBLING_FAST_REDEPLOY="`aws ecs update-service`",
    SAAS_ENGINE="Azure OpenAI on the AI Foundry account", SAAS_ENGINE_ID="azure-openai",
    SIBLING_SAAS_ENGINE="Amazon Bedrock", SIBLING_SAAS_ENGINE_ID="bedrock",
    PUBLISH_STORE="Azure Blob Storage (private per-engagement container, SAS access)", SIBLING_PUBLISH_STORE="Amazon S3",
    PUBLISH_STORE_SHORT="Azure Blob Storage",
    SAAS_ENV_VARS="`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`, `FOUNDRY_*`",
    SECRETS_ROWS="| Secret | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | OIDC identity for every workflow |\n| Secret | `FRONTDOOR_CERTIFICATE_PFX_PASSWORD` | Front Door certificate (`100` checks it, `210` verify uses it) |",
    VARS_ROWS="| Variable | `TFSTATE_RESOURCE_GROUP`, `TFSTATE_STORAGE_ACCOUNT`, `TFSTATE_CONTAINER`, `AZURE_REGION_SHORT`, `AZURE_TARGET_SUBSCRIPTION_NAME` | State backend and region for the roots |\n| Variable | `CNA_ENTRA_CLIENT_ID`, `CNA_NEXTAUTH_URL`, `KEY_VAULT_NAME`, `APPLICATION_INSIGHTS_NAME`, `FRONTDOOR_CERTIFICATE_NAME`, `ALZ_DIAGNOSTICS_MANAGE` | Environment wiring (several are written back by Terraform) |\n| Variable | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_RECOMMENDATION_AGENT_ID`, `CNA_AZURE_MCP_ENDPOINT`, `CNA_AWS_MCP_ENDPOINT`, `CNA_DRAWIO_MCP_URL` | Optional AI / MCP integrations |",
    STATUS_NOTE="", AGENT_STATUS_NOTE="",
    CHANGELOG_EXTRA="- The dev release catalog (`.deployment-catalog/dev/`) carries over from the core so `230-image-update` and rollback resolution see the environment's real history.\n",
    REVIEW_TABLE="| [R-001](#r-001--security-review-before-the-first-byo-api-deploy) | Security review of the bring-your-own AI key path and the Anthropic/OpenAI firewall egress | Security | Open — before the first `byo-api` deploy |\n| [R-002](#r-002--required-reviewers-on-the-hub-environment) | `hub` environment required reviewers for prod applies | Repository admin | Open |",
    REVIEW_BODY="""## R-001 — Security review before the first `byo-api` deploy

**Problem**
`ai_mode: byo-api` stores admin-entered Anthropic/OpenAI API keys AES-256-GCM encrypted in the
application database and opens Azure Firewall egress to `api.anthropic.com` and `api.openai.com`.
The implementation lives in the core repository and is complete and tested; CBTS engineering
standards require a human security review before it carries customer traffic.

**Required owner**
Security.

**Required action**
Complete the core repository's `REVIEW.md` → R-011 (it lists the exact files and questions), then
record the outcome here.

**Impact if unresolved**
`byo-api` cannot be offered to a customer from this appliance. `saas` is unaffected.

---

## R-002 — Required reviewers on the `hub` environment

**Problem**
`210-deploy`'s prod `apply` job runs under the `hub` GitHub environment, whose required
reviewers are the human approval gate for production changes — the same gate the core used. A
freshly created repository has no environments and therefore no gate.

**Required owner**
Repository admin.

**Required action**
Create the `dev`, `prod` and `hub` environments; give `hub` the same required reviewers the core
repository's `hub` environment has; register the OIDC federated credential for the prod deploy
identity against subject `environment:hub` of this repository.

**Impact if unresolved**
Prod deploys either fail OIDC or, worse, run without human approval.
""",
    TODO_RANGE="T-101 – T-102",
    TODO_BODY="""### T-101 — Verify the first `saas` apply is a pure re-addressing

- **Priority:** High
- **Description:** The import from the core added `count` to the AI module, the four Foundry role
  assignments and the Foundry private endpoint, each with a `moved` block. On an environment that
  already exists (dev), the first `210-deploy` plan must show only those `moved` annotations plus
  three in-place Container App env updates (`CNA_AI_MODE`, `CNA_APPLIANCE_CLOUD`,
  `CNA_AI_ENGINE_DEFAULT`) — no create, no destroy.
- **Recommended action:** Run `210-deploy` for dev in `saas` mode, stop at the plan artifact, and
  read it line by line before approving. A destroy of `module.ai` means a `moved` block is missing.
- **Status:** Open

### T-102 — Add this repository to the shared project board

- **Priority:** Low
- **Description:** `230-image-update`'s `update-available` issues should land on the one project
  board shared with the core and the sibling appliance.
- **Dependencies:** The core repository's `REVIEW.md` → R-012 (token decision).
- **Recommended action:** Add a SHA-pinned `actions/add-to-project` workflow on `issues: opened` and
  `pull_request: opened`, identical in both appliances.
- **Status:** Blocked on the core's R-012
""",
  ),
  "aws": dict(
    CLOUD_TITLE="AWS", SIBLING_TITLE="Azure",
    COMPUTE="ECS Fargate + ALB, RDS PostgreSQL, Secrets Manager, CloudFront + WAF, Bedrock",
    SIBLING_COMPUTE="Container Apps, PostgreSQL Flexible Server, Key Vault, Front Door + WAF, Azure Firewall, AI Foundry",
    STATE_BACKEND="`s3` + DynamoDB lock table (`region`, `region_short`, `tfstate_bucket`, `tfstate_lock_table`)",
    SIBLING_STATE_BACKEND="`azurerm`: storage account + container (`location`, `region_short`, `tfstate_resource_group`, `tfstate_storage_account`, `tfstate_container`)",
    OIDC_SECRETS="`aws-actions/configure-aws-credentials` — `AWS_DEPLOY_ROLE_ARN`",
    SIBLING_OIDC_SECRETS="`azure/login` — `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`",
    VAULT="AWS Secrets Manager", SIBLING_VAULT="Azure Key Vault",
    FAST_REDEPLOY="`aws ecs update-service`", SIBLING_FAST_REDEPLOY="`az containerapp update`",
    SAAS_ENGINE="Amazon Bedrock", SAAS_ENGINE_ID="bedrock",
    SIBLING_SAAS_ENGINE="Azure OpenAI on the AI Foundry account", SIBLING_SAAS_ENGINE_ID="azure-openai",
    PUBLISH_STORE="Amazon S3 (private bucket, pre-signed access)", SIBLING_PUBLISH_STORE="Azure Blob Storage",
    PUBLISH_STORE_SHORT="Amazon S3",
    SAAS_ENV_VARS="`CNA_BEDROCK_MODEL_ID`, `CNA_BEDROCK_INFERENCE_PROFILE_ARN`",
    SECRETS_ROWS="| Secret | `AWS_DEPLOY_ROLE_ARN` | OIDC deploy role assumed by every workflow |\n| Secret | `CNA_AWS_ROLE_ARN`, `CNA_PUBLISH_BUCKET` | Portal publishing role and bucket (`320`) |",
    VARS_ROWS="| Variable | `TFSTATE_BUCKET`, `TFSTATE_LOCK_TABLE`, `AWS_REGION`, `AWS_REGION_SHORT` | State backend and region for the roots |\n| Variable | `CNA_ENTRA_CLIENT_ID`, `CNA_NEXTAUTH_URL` | Environment wiring |\n| Variable | `CNA_AZURE_MCP_ENDPOINT`, `CNA_AWS_MCP_ENDPOINT`, `CNA_DRAWIO_MCP_URL` | Optional MCP integrations |",
    STATUS_NOTE="\n> **Status:** the AWS Terraform is authored and validates, but has never been applied. `210-deploy` and the other operational workflows fail fast until the AWS account, the state backend and the OIDC deploy role in [`REVIEW.md`](REVIEW.md) (R-001 – R-003) exist. Their inputs are already final and identical to the Azure appliance's, so operators learn one dialog.\n",
    AGENT_STATUS_NOTE="\n## Current status\n\nThe Terraform is complete and validates. `210-deploy`, `000`, `100`, `220`, `330`,\n`340`, `350` and `360` are scaffolds that fail fast until `REVIEW.md` R-001 – R-003\nare resolved. When implementing them, keep every input exactly as it is (the\nAzure appliance has the same ones) and follow the Azure sibling's job shape step\nfor step; `230` and `300` are already real.\n",
    CHANGELOG_EXTRA="- `000`, `100`, `220`, `330`, `340`, `350` and `360` are fail-fast scaffolds with the same inputs as the Azure appliance; `210-deploy` is the core's `212` scaffold renamed. All of them point at `REVIEW.md` R-001 – R-003 and `TODO.md` T-101 / T-102.\n",
    REVIEW_TABLE="""| [R-001](#r-001--aws-account-and-administrative-access) | AWS account + administrative access for the first deploy | AWS account owner | Open |
| [R-002](#r-002--terraform-s3-state-backend-created-out-of-band) | Terraform S3 state bucket + DynamoDB lock table | AWS account owner | Open |
| [R-003](#r-003--github-oidc-deploy-role-wired-into-ci) | GitHub OIDC deploy role in `AWS_DEPLOY_ROLE_ARN` | Repository admin | Open |
| [R-004](#r-004--acm-certificates-and-custom-domain-decision) | ACM certificates + custom-domain decision | DNS / domain owner | Open |
| [R-005](#r-005--amazon-bedrock-model-access-opt-in) | Bedrock foundation-model access opt-in (`ai_mode: saas`) | AWS account owner | Open |
| [R-006](#r-006--security-review-before-the-first-byo-api-deploy) | Security review of the bring-your-own AI key path and provider egress | Security | Open — before the first `byo-api` deploy |
| [R-007](#r-007--required-reviewers-on-the-hub-environment) | `hub` environment required reviewers for prod applies | Repository admin | Open |""",
    REVIEW_BODY="""## R-001 — AWS account and administrative access

**Problem**
`infra/terraform/modules/` declares the full AWS stack (eight modules, 90 resources) and it has
never been applied: there is no AWS account, administrative principal or bootstrap identity.

**Required owner**
AWS account owner / cloud finance approver.

**Required action**
Provision or nominate the account(s) for `dev` and `prod`, confirm the region (`var.region`; a
fixed `us-east-1` aliased provider serves the CloudFront-scoped WAF regardless), and grant an
engineer a principal able to create IAM, OIDC, S3, DynamoDB, VPC, ECS, RDS, CloudFront, WAFv2,
KMS, Secrets Manager and CloudWatch resources.

**Impact if unresolved**
Every workflow in this repository except `230` and `300` stays a fail-fast scaffold.

---

## R-002 — Terraform S3 state backend created out of band

**Problem**
Every root uses an empty `backend "s3" {}`; the bucket and lock table must exist before the first
`terraform init` — Terraform cannot create the backend it is about to use. `000-bootstrap-backend`
will create them once R-001 and R-003 exist; until then they are created by hand.

**Required owner**
AWS account owner (depends on R-001).

**Required action**
Create a versioned, SSE-KMS bucket and a DynamoDB table with a `LockID` (S) partition key, then
record `TFSTATE_BUCKET`, `TFSTATE_LOCK_TABLE`, `AWS_REGION` and `AWS_REGION_SHORT` as repository
variables (state keys are `<env>/platform.tfstate` and `<env>/workload.tfstate`).

**Impact if unresolved**
No Terraform command past `validate` can run.

---

## R-003 — GitHub OIDC deploy role wired into CI

**Problem**
The identity module provisions the GitHub OIDC provider and a deploy role and exports
`github_deploy_role_arn`; nothing consumes it yet, and the role cannot exist before R-001.

**Required owner**
Repository admin together with the AWS account owner.

**Required action**
Apply (or import) the identity module's OIDC provider and role with this repository as the trusted
subject, then store the role ARN as the `AWS_DEPLOY_ROLE_ARN` secret. Long-lived access keys are
not an interim option — the platform is OIDC-only.

**Impact if unresolved**
No workflow can authenticate to AWS.

---

## R-004 — ACM certificates and custom-domain decision

**Problem**
`alb_certificate_arn` and `acm_certificate_arn` are inputs (default `null`) because minting an
unvalidated certificate hangs on DNS validation. Someone has to decide the customer-facing domain
and who owns its DNS.

**Required owner**
DNS / domain owner.

**Required action**
Choose the domain, issue the two certificates (the CloudFront one in `us-east-1`) and record the
ARNs as repository variables; or accept the default CloudFront domain for `dev`.

**Impact if unresolved**
HTTPS on the ALB is skipped and CloudFront serves its default certificate.

---

## R-005 — Amazon Bedrock model access opt-in

**Problem**
`ai_mode: saas` invokes Bedrock through the task role and the inference profile Terraform creates,
but foundation-model access must be enabled manually in the Bedrock console per account and
region before any invocation succeeds. The model id in `infra/terraform/modules/ai/variables.tf`
is also several generations old and must be verified before the first apply.

**Required owner**
AWS account owner.

**Required action**
Enable access for the chosen Anthropic model in the deployment region and update `model_ids` to a
current id. Alternatively deploy with `ai_mode: byo-api`, which needs no Bedrock access at all.

**Impact if unresolved**
`saas` deploys succeed but every AI call fails with an access error.

---

## R-006 — Security review before the first `byo-api` deploy

**Problem**
`ai_mode: byo-api` stores admin-entered Anthropic/OpenAI API keys AES-256-GCM encrypted in the
application database, and the ECS tasks reach `api.anthropic.com` / `api.openai.com` through the
NAT gateway — there is no FQDN egress filter in the AWS platform today. The implementation lives in
the core repository and is complete and tested; CBTS engineering standards require a human
security review before it carries customer traffic.

**Required owner**
Security.

**Required action**
Complete the core repository's `REVIEW.md` → R-011, decide whether the AWS appliance needs an
outbound FQDN control (AWS Network Firewall or a proxy) before its first `byo-api` deploy, and
record the outcome here.

**Impact if unresolved**
`byo-api` cannot be offered to a customer from this appliance.

---

## R-007 — Required reviewers on the `hub` environment

**Problem**
`210-deploy`'s prod `apply` job runs under the `hub` GitHub environment, whose required
reviewers are the human approval gate for production changes. A freshly created repository has no
environments and therefore no gate.

**Required owner**
Repository admin.

**Required action**
Create the `dev`, `prod` and `hub` environments; give `hub` the same required reviewers the core
repository's `hub` environment has; trust subject `environment:hub` of this repository in the OIDC
deploy role (R-003).

**Impact if unresolved**
Prod deploys either fail OIDC or run without human approval.
""",
    TODO_RANGE="T-101 – T-103",
    TODO_BODY="""### T-101 — Implement `210-deploy` as a functional AWS release

- **Priority:** High
- **Description:** `210-deploy` is the core's `212` scaffold: it carries the exact input contract
  of the Azure appliance's `210` (`environment`, images, `previous_*_image`, `deploy_mode`,
  `ai_mode`, plus the `workflow_call` trigger `230` uses) but every job fails fast.
- **Dependencies:** `REVIEW.md` R-001 – R-003; R-005 for `saas`.
- **Recommended action:** Replace the guards job by job following the Azure sibling's shape:
  policy gates → platform plan/apply → workload plan/apply (with `-var ai_mode`) → migrator task →
  health verification → release-catalog write (`ai_mode`, `source_repo`, `source_manifest_run_id`
  included, so `230` keeps working). Reuse `scripts/ci/evaluate_deployment_evidence.py`. The
  post-apply identity step is the Entra redirect-URI sync against the CloudFront domain — easy to
  forget because it is not Terraform.
- **Status:** Blocked

### T-102 — Implement the operational scaffolds

- **Priority:** High
- **Description:** `000`, `100`, `220`, `330`, `340`, `350`, `360` fail fast with the Azure
  appliance's inputs. Each header says what the real job does.
- **Dependencies:** T-101's prerequisites.
- **Recommended action:** Implement in band order; keep the inputs byte-identical to the Azure
  sibling; give `350` its daily schedule only once dev has been deployed.
- **Status:** Blocked

### T-103 — Add this repository to the shared project board

- **Priority:** Low
- **Description:** `230-image-update`'s `update-available` issues should land on the one project
  board shared with the core and the sibling appliance.
- **Dependencies:** The core repository's `REVIEW.md` → R-012 (token decision).
- **Recommended action:** Add a SHA-pinned `actions/add-to-project` workflow on `issues: opened` and
  `pull_request: opened`, identical in both appliances.
- **Status:** Blocked on the core's R-012
""",
  ),
}[cloud]
spec.update(CLOUD=cloud, REPO=repo, SIBLING_REPO=sibling, DATE=date, CORE_COMMIT=core_commit)

for name in ("README.md", "CLAUDE.md", "CHANGELOG.md", "REVIEW.md", "TODO.md"):
    s = (T / (name + ".tmpl")).read_text()
    for k, v in spec.items():
        s = s.replace(f"@@{k}@@", v)
    leftover = [w for w in s.split() if w.startswith("@@")]
    assert not leftover, f"{name}: unresolved placeholders {leftover}"
    pathlib.Path(name).write_text(s)
print("documents rendered")
EOF

# ── Secrets baseline: same scanner config as the core, entries re-scanned for this tree ──
# The core baseline already carries the exclude pattern and plugin set; passing
# --exclude-files again makes `scan --baseline` drop every result instead of
# refreshing them, so the baseline is the only configuration source here. The
# entries it records are the same hand-audited false positives the core holds
# (secret *names* in Terraform maps, an Authorization header, an image digest),
# now under this repository's paths.
# detect-secrets discovers files through `git ls-files`, so the tree must be
# staged before the scan or the fresh files are simply not seen.
git add -A
cp "$CORE/.secrets.baseline" .secrets.baseline
"$DS" scan --baseline .secrets.baseline
git add -A
echo "== tree assembled at $OUT ($(git status --short | wc -l) files staged)"
