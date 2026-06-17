# CNA TODO

> Last updated: 2026-06-16

This is the canonical open-task list. Historical gap analysis, footprint review
notes, ADRs, and audit artifacts have been migrated or consolidated so active
work is tracked here.

## Final Main Sync

- [x] Merge or otherwise land all open pull request changes.
- [x] Confirm GitHub has no open pull requests.
- [x] Confirm GitHub has no open Issues.
- [x] Update app/package version metadata to `0.8 beta`.
- [x] Update changelog, README, ADF index, and GitHub Wiki for beta readiness.

## Open Network Review Findings

- [x] P1. Enforce Foundry private DNS validation from inside the CNA web Container App against the deployed `services.ai.azure.com` endpoint path.
- [x] P1. Enforce Foundry Claude inference validation with managed identity only, with local authentication disabled and no API-key fallback required.
- [x] P1. Tighten Front Door private-link approval automation so repeat deploys fail on ambiguous pending requests instead of approving the wrong connection.
- [ ] P2. Review Azure Firewall allowlist coverage after first live deployment and expand it only if the workload or platform telemetry needs additional egress endpoints.
- [x] P2. Narrow the Front Door WAF auth-path allow rule to expected GET/POST authentication flows.
- [ ] P2. Re-check the narrowed Front Door WAF auth-path allow rule after customer sign-in testing.

## Redeploy And Validation

- [ ] P1. Run workflow `010-validate-prereqs.yml` and resolve any missing GitHub Secrets, Variables, Azure OIDC, RBAC, or tfstate backend access.
- [x] P1. Register `Microsoft.AlertsManagement` in the Azure subscription so Application Insights smart-detection alert deployment does not fail.
- [x] P1. Validate `AZURE_SUBSCRIPTION_ID` and `AZURE_TARGET_SUBSCRIPTION_NAME` so preflight and deploy fail if the repo is pointed at the wrong subscription.
- [ ] P1. Run workflow `030-build-images.yml` to publish current immutable GHCR image tags.
- [ ] P1. Run workflow `031-deploy-azure.yml` for `dev`.
- [ ] P1. Confirm workflow `031-deploy-azure.yml` updated `CNA_NEXTAUTH_URL`, `KEY_VAULT_NAME`, and `APPLICATION_INSIGHTS_NAME` from Terraform outputs.
- [ ] P1. Capture the live Front Door hostname only from current Terraform/workflow outputs; do not rely on older documented `azurefd.net` references.
- [ ] P1. Update the Entra redirect URI to `https://<frontdoor-host>/api/auth/callback/microsoft-entra-id`.
- [ ] P1. Rerun workflow `031-deploy-azure.yml` so corrected runtime values are applied.
- [ ] P1. Run workflow `011-sync-keys.yml` after Key Vault exists to validate runtime secrets.
- [ ] P1. Verify Front Door URL, `/api/health`, Entra sign-in, Application Insights telemetry, and all three Container App revisions.
- [ ] P2. Run workflow `032-teardown.yml` for `dev` with `confirm=DESTROY`, `destroy_tfstate_backend=false`, and `delete_drifted_resources=false`.
- [ ] P2. Confirm the `032` cleanup preview lists only CNA-owned workload resources and approved Azure-managed auxiliary groups, then rerun `032` with `delete_drifted_resources=true`.

## Beta Acceptance

- [ ] P3. Run multi-subscription Azure discovery against a real customer-like tenant.
- [ ] P3. Validate findings, risk scoring, compliance mappings, FinOps signals, and BC/DR signals against discovered data.
- [ ] P3. Generate and review deliverables end to end, including encyclopedia report output.
- [ ] P3. Validate the interactive assessment journey, role-based access, reviewer flow, and client portal access.
- [ ] P3. Confirm no code changes are required after Beta validation; if issues appear, convert them into specific implementation tasks.

## Cost And Footprint Follow-Ups

- [ ] P3. Decide whether `dev` should keep Front Door Premium/WAF for parity or move to Standard/remove Front Door for cost savings.
- [ ] P3. Decide whether `dev` should keep prod-grade PostgreSQL (`GP_Standard_D2s_v3`, 30-day geo-redundant backup) or use a cheaper dev SKU after policy gates are finalized.
- [ ] P3. Document an idle-dev cadence using workflow `032` teardown and workflow `031` redeploy when active development resumes.
- [ ] P3. Review production PostgreSQL CPU, memory, storage, and connection metrics after live traffic before right-sizing.
- [ ] P3. Add Azure budget/cost alerts for Foundry Claude usage and platform resource groups.
- [ ] P3. Add per-engagement AI request limits if live copilot usage requires stronger cost controls.
- [ ] P3. Review production Container Apps replica ceilings after observed traffic; reduce max replicas only if headroom remains acceptable.

## Product Enhancements

- [ ] P3. Complete Japanese glossary/native-speaker review for the JA report path before enabling client-facing JA output.
- [ ] P3. Wire live MCP server endpoints for Azure, AWS, and draw.io integrations.
- [ ] P3. Extend CISA ZTMM v2 mappings for WAF-related findings into the Applications and Workloads pillar where appropriate.

## Closed Or Superseded

- Sprint 5 WCAG/W3C/OWASP audit artifacts were removed after validation because mitigations are recorded in `CHANGELOG.md` and code-level markers exist for the implemented fixes.
- Historical ADRs were moved to the GitHub Wiki.
- The previous gap analysis and footprint review notes were consolidated into this TODO.
- The Foundry privatization architecture decision and related workflow/doc updates were completed and committed on 2026-06-15.
