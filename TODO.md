# CNA TODO

> Last updated: 2026-06-14

This is the canonical open-task list. Historical gap analysis, footprint review
notes, ADRs, and audit artifacts have been migrated or consolidated so active
work is tracked here.

## Redeploy And Validation

- [ ] Run workflow `010-validate-prereqs.yml` and resolve any missing GitHub Secrets, Variables, Azure OIDC, RBAC, or tfstate backend access.
- [ ] Run workflow `032-teardown.yml` for `dev` with `confirm=DESTROY` and `destroy_tfstate_backend=false`.
- [ ] Confirm the `032` cleanup preview lists only CNA-owned workload resources and approved Azure-managed auxiliary groups.
- [ ] Run workflow `030-build-images.yml` to publish current immutable GHCR image tags.
- [ ] Run workflow `031-deploy-azure.yml` for `dev`.
- [ ] Update `CNA_NEXTAUTH_URL`, `KEY_VAULT_NAME`, and `APPLICATION_INSIGHTS_NAME` from Terraform outputs.
- [ ] Update the Entra redirect URI to `https://<frontdoor-host>/api/auth/callback/microsoft-entra-id`.
- [ ] Rerun workflow `031-deploy-azure.yml` so corrected runtime values are applied.
- [ ] Run workflow `011-sync-keys.yml` after Key Vault exists to validate runtime secrets.
- [ ] Verify Front Door URL, `/api/health`, Entra sign-in, Application Insights telemetry, and all three Container App revisions.

## Beta Acceptance

- [ ] Run multi-subscription Azure discovery against a real customer-like tenant.
- [ ] Validate findings, risk scoring, compliance mappings, FinOps signals, and BC/DR signals against discovered data.
- [ ] Generate and review deliverables end to end, including encyclopedia report output.
- [ ] Validate the interactive assessment journey, role-based access, reviewer flow, and client portal access.
- [ ] Confirm no code changes are required after Beta validation; if issues appear, convert them into specific implementation tasks.

## Cost And Footprint Follow-Ups

- [ ] Decide whether `dev` should keep Front Door Premium/WAF for parity or move to Standard/remove Front Door for cost savings.
- [ ] Decide whether `dev` should keep prod-grade PostgreSQL (`GP_Standard_D2s_v3`, 30-day geo-redundant backup) or use a cheaper dev SKU after policy gates are finalized.
- [ ] Document an idle-dev cadence using workflow `032` teardown and workflow `031` redeploy when active development resumes.
- [ ] Review production PostgreSQL CPU, memory, storage, and connection metrics after live traffic before right-sizing.
- [ ] Add Azure budget/cost alerts for Foundry Claude usage and platform resource groups.
- [ ] Add per-engagement AI request limits if live copilot usage requires stronger cost controls.
- [ ] Review production Container Apps replica ceilings after observed traffic; reduce max replicas only if headroom remains acceptable.

## Product Enhancements

- [ ] Complete Japanese glossary/native-speaker review for the JA report path before enabling client-facing JA output.
- [ ] Wire live MCP server endpoints for Azure, AWS, and draw.io integrations.
- [ ] Extend CISA ZTMM v2 mappings for WAF-related findings into the Applications and Workloads pillar where appropriate.

## Closed Or Superseded

- Sprint 5 WCAG/W3C/OWASP audit artifacts were removed after validation because mitigations are recorded in `CHANGELOG.md` and code-level markers exist for the implemented fixes.
- Historical ADRs were moved to the GitHub Wiki.
- The previous gap analysis and footprint review notes were consolidated into this TODO.
