"""Findings for the ``terraform-azure`` area (Requirement 3 hardening).

This is a *verify-then-close-gaps* record for the eight Azure provider modules
(``ai, compute, database, identity, observability, runtime, security,
storage``) under ``infra/terraform/providers/azure/`` and the dev/prod
environments under ``infra/terraform/environments/azure/``. The audit covered
tags, diagnostic settings, network exposure, and SKU tiers (design section
"3. Terraform Azure", Requirements 3.1 and 3.3).

Scope gate. R-007 (Azure provider registration) is "Resolved — no longer
required" but *not* CLOSED, so per Requirement 10.3 its subject stays out of
automated scope: nothing here touches provider registration. R-008 (live Azure
beta acceptance sign-off) is the open Azure blocker and is recorded separately
as an ``Escalation_Record`` by spec task 6.2 — not here. These records carry
no ``blocker_id`` and are all fixable/informational area findings.

What the audit confirmed compliant (recorded ``INFORMATIONAL`` so the plan
reflects what was checked, not only what broke):

  * **Tags.** Every module threads ``var.tags`` (the ``ai`` module merges in
    ``local.foundry_tags``); the environment roots build a single ``local.tags``
    map and pass it to every module and platform resource. No untagged resource
    was found.
  * **Diagnostic settings.** The ``observability`` module wires
    ``azurerm_monitor_diagnostic_setting`` for every app-plane target (Key
    Vault, storage, PostgreSQL, Foundry, Container Apps, Front Door) and the
    platform root adds firewall/NSG/VNet-flow-log coverage. The storage
    module's ``CKV2_AZURE_21`` blob-diagnostics skip is covered at the account
    level by this wiring.
  * **SKU tiers.** Front Door is ``Premium_AzureFrontDoor`` (WAF-capable), the
    egress firewall is ``Premium``, PostgreSQL is ``GP_Standard_D2s_v3`` with
    30-day backups and geo-redundant backup, and the Key Vault is ``standard``
    (software-protected) — appropriate for secret storage; HSM (premium) is not
    required here.
  * **Network exposure.** PostgreSQL, the AI Foundry account, and the Container
    Apps environment are private (delegated subnet / private endpoints /
    ``public_network_access_enabled = false``); NSGs deny cross-VNet inbound by
    default; the Key Vault runs deny-by-default with a transient runner-IP
    allow window.

The residual gap this task closed, and the live-environment drift Requirement
3.3 requires recording, are the two non-informational findings below. These
records are consumed by the consolidation step (spec task 14.1).
"""

from __future__ import annotations

from cna.review.model import Finding, Severity

_AREA = "terraform-azure"

# The four Azure environment roots swept by ``terraform validate`` (spec task
# 6.2). Every root declares ``backend "azurerm" {}``, so init runs with
# ``-backend=false`` (no live state backend is contacted) before validate.
AZURE_ROOTS: tuple[str, ...] = (
    "infra/terraform/environments/azure/dev/platform",
    "infra/terraform/environments/azure/dev/workload",
    "infra/terraform/environments/azure/prod/platform",
    "infra/terraform/environments/azure/prod/workload",
)

# The owning REVIEW.md blocker for live Azure beta acceptance sign-off. Open, so
# its subject is out of automated scope and the finding below is forced to an
# ``Escalation_Record`` by the scope gate (Requirement 3.4 / 10.4).
_R008 = "R-008"


def terraform_azure_findings() -> list[Finding]:
    """Return the Requirement 3 findings recorded for this area."""
    return [
        Finding(
            area=_AREA,
            severity=Severity.MEDIUM,
            proposed_action=(
                "Add a deny-by-default network_rules block "
                '(default_action = "Deny", bypass = ["AzureServices"]) to the '
                "application storage account so it is no longer reachable from "
                "arbitrary internet source IPs. Application traffic uses the "
                "private endpoint created in the security module; keep "
                "public_network_access_enabled = true for the Terraform/static-"
                "website bootstrap window and ignore_changes on network_rules[0]"
                ".ip_rules so the deploy/drift workflows can add and remove the "
                "transient runner IP without perpetual drift — mirroring the "
                "Key Vault (identity module) and the flow-log storage account "
                "(platform root). Applied in this task."
            ),
            dedup_key="terraform-azure:storage-account-network-rules-deny-default",
            subject="infra/terraform/providers/azure/storage/main.tf::azurerm_storage_account.this",
        ),
        Finding(
            area=_AREA,
            severity=Severity.LOW,
            proposed_action=(
                "Record drift of the live-but-stale Azure dev environment from "
                "the current Terraform definition. The code carries dev-only "
                "workarounds pinned to live-state facts — the AI Foundry account "
                "name bumped to '-aif2' to sidestep the soft-delete graveyard of "
                "the reserved '-aif' name, and the gpt-chat-latest deployment "
                "re-declared in Terraform after it was lost with that name bump. "
                "Reconcile once the soft-deleted '-aif' account is purged or its "
                "retention lapses (revert the account name to 'cna-dev-eus2-aif'). "
                "Live reconciliation runs through the 350-drift-dev.yml workflow "
                "against the live subscription (human-observed); it is recorded "
                "here, not auto-applied."
            ),
            dedup_key="terraform-azure:dev-environment-live-drift",
            subject="infra/terraform/environments/azure/dev/workload/main.tf::module.ai",
        ),
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified compliant: tags thread through every module "
                "(local.tags in the roots; var.tags plus local.foundry_tags in "
                "ai); diagnostic settings cover every app-plane target via the "
                "observability module plus platform firewall/NSG/flow-log "
                "coverage; SKU tiers are production-appropriate (Front Door "
                "Premium, firewall Premium, PostgreSQL GP with geo-redundant "
                "backup, Key Vault standard for secret storage); and network "
                "exposure is private-endpoint / delegated-subnet based with "
                "deny-by-default NSGs. terraform fmt is clean across all eight "
                "modules and both environments. Guard against regression."
            ),
            dedup_key="terraform-azure:best-practice-baseline-verified",
            subject="infra/terraform/providers/azure",
        ),
    ]


def terraform_azure_verify_findings() -> list[Finding]:
    """Return the Requirement 3.2/3.4 verification + escalation records.

    Spec task 6.2. Two records, kept separate from the 6.1 audit findings
    (:func:`terraform_azure_findings`) so the ``terraform validate`` gate and
    the R-008 escalation are attributable to this task:

      * **3.2 — ``terraform validate`` sweep (fixable, INFORMATIONAL).** Records
        the result of running ``terraform fmt -check`` (clean, recursive),
        ``terraform init -backend=false`` (no live state backend contacted), and
        ``terraform validate`` against each of the four Azure environment roots
        (:data:`AZURE_ROOTS`). All four passed with Terraform v1.15.8. Recorded
        so the plan captures that validate ran for *every* evaluation of the
        Azure Terraform (Requirement 3.2), not only that it happened to pass. If
        ``terraform`` were unavailable, this would instead be recorded as a
        coverage-gap finding rather than a silent pass — here the tool was
        present and every root validated.

      * **3.4 — live acceptance sign-off (escalation, R-008).** Carries
        ``blocker_id="R-008"``. Live Azure beta-exit acceptance sign-off is a
        product-owner decision against the live subscription — it cannot be
        performed by engineering and MUST NOT be auto-applied (escalation-only,
        no live apply). The scope gate (R-008 is Open) turns this finding into an
        ``Escalation_Record`` (Requirement 3.4 / 10.4).

    These records are consumed by the consolidation step (spec task 14.1).
    """
    roots = ", ".join(AZURE_ROOTS)
    return [
        Finding(
            area=_AREA,
            severity=Severity.INFORMATIONAL,
            proposed_action=(
                "Verified compliant: terraform fmt -check is clean (recursive) "
                "across the Azure provider modules and environment roots, and "
                "terraform init -backend=false + terraform validate succeed for "
                f"every Azure environment root ({roots}) on Terraform v1.15.8. "
                "init uses -backend=false so no live azurerm state backend is "
                "contacted; no terraform apply is run. Re-run this validate sweep "
                "on every evaluation of the Azure Terraform (Requirement 3.2) and "
                "guard against a validate regression."
            ),
            dedup_key="terraform-azure:terraform-validate-sweep",
            subject="infra/terraform/environments/azure",
        ),
        Finding(
            area=_AREA,
            severity=Severity.HIGH,
            proposed_action=(
                "Live Azure beta-exit acceptance sign-off (REVIEW.md R-008) is "
                "required before the 0.8 beta can exit: a product owner must "
                "validate the deployed Azure environment against the live "
                "subscription and sign off. This is a human-gated decision that "
                "cannot be performed by engineering — escalate; do not attempt a "
                "live apply or any automated live acceptance (escalation-only)."
            ),
            dedup_key="terraform-azure:gated:live-acceptance-sign-off",
            subject="infra/terraform/environments/azure",
            blocker_id=_R008,
        ),
    ]
