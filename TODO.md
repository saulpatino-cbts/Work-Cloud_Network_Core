# CNA Platform — Active TODO

> **Status as of 2026-05-28 · Version 1.0.0 Released**
> Version 1.0.0 release stage is complete. All delivery phases, Beta hardening sprints (1–4), and the Sprint 5 WCAG/W3C/OWASP security audit are signed off and closed.
> All findings resolved, all rules active, and platform is ready for production.

---

## ~~Alpha Completed (2026-04-14)~~

~~Everything below shipped and is live on the dev environment at SHA `ace931c`.~~

| Feature | Status |
| --- | --- |
| ~~Platform architecture (3-container, PostgreSQL, Entra ID)~~ | ✅ Done |
| ~~Terraform modules (all Azure resources)~~ | ✅ Done |
| ~~GitHub Actions workflows (000–031)~~ | ✅ Done |
| ~~Entra ID auth + OIDC federation~~ | ✅ Done |
| ~~First Terraform deployment (dev)~~ | ✅ Done |
| ~~Per-subscription sync groups (one `DiscoveryJob` per credential)~~ | ✅ Done |
| ~~Multi-subscription topology merge (inventory + presentations + deliverables)~~ | ✅ Done |
| ~~Findings count — unique issue groups vs. raw count~~ | ✅ Done |
| ~~Five assessment types (COMPREHENSIVE HTML + 4 Markdown)~~ | ✅ Done |
| ~~Comprehensive Assessment HTML output (fixed system prompt conflict)~~ | ✅ Done |
| ~~MS Learn enrichment (live fetch at generation time)~~ | ✅ Done |
| ~~Interactive Assessment: AI generation on every create/recreate~~ | ✅ Done |
| ~~Interactive Assessment: "View Report" + "Dashboard" split in portal~~ | ✅ Done |
| ~~Presentation dashboard: all pages use merged topology (fixes "1 subscription")~~ | ✅ Done |
| ~~Error surfacing in create-assessment-button~~ | ✅ Done |

---

## Beta — Step 1: Fresh Environment Deployment

The dev environment resources are being deleted. Redeploy from scratch using the
sequence below. All code handles a blank Azure environment — migrations run in the
Docker migrator stage, no seed data is required.

### 1a. Verify GitHub Secrets & Variables Are Still Set

Before deploying, confirm all required values are in GitHub Settings:

**Secrets:**

| Secret | Status |
| --- | --- |
| `AZURE_CLIENT_ID` | ⚠️ Verify still valid after resource deletion |
| `AZURE_TENANT_ID` | Should be unchanged |
| `AZURE_SUBSCRIPTION_ID` | Should be unchanged |
| `CNA_POSTGRES_ADMIN_PASSWORD` | Should be unchanged |
| `CNA_ENTRA_CLIENT_SECRET` | ⚠️ Verify — Entra secret may have rotated |
| `CNA_NEXTAUTH_SECRET` | Should be unchanged |

**Variables:**

| Variable | Notes |
| --- | --- |
| `TFSTATE_RESOURCE_GROUP` | `rg-cna-tfstate` — tfstate RG survives env deletion |
| `TFSTATE_STORAGE_ACCOUNT` | `stcnatfstate` — survives env deletion |
| `TFSTATE_CONTAINER` | `tfstate` — survives env deletion |
| `CNA_ENTRA_CLIENT_ID` | Should be unchanged |
| `CNA_NEXTAUTH_URL` | Reset to `none` until new Front Door hostname is known |
| `CNA_AZURE_OPENAI_DEPLOYMENT` | Should be unchanged (e.g. `gpt-4o`) |
| `APPLICATION_INSIGHTS_NAME` | Reset to `none` — **auto-updated by 031 after apply** |
| `KEY_VAULT_NAME` | Reset to `none` — **auto-updated by 031 after apply** |

> The Terraform state RG (`rg-cna-tfstate`) is isolated from the workload RG
> (`rg-cna-dev-scus`) and is NOT deleted when tearing down the dev environment.
> Terraform state is preserved — the next `terraform apply` will create fresh resources
> in the workload RG rather than re-importing.

### 1b. Run Workflow 010 — Validate Prerequisites

- [ ] Run `010-validate-prereqs.yml` → confirm all secrets/variables/OIDC pass

### 1c. Build Container Images

- [ ] Push to main OR manually run `030-build-images.yml`
- [ ] Confirm three images appear in GitHub Packages (cna-api, cna-worker, cna-web)
- [ ] Note the SHA tag from the build manifest (`.deployment-catalog/latest-build.json`)

### 1d. Deploy Azure Infrastructure

- [ ] Run `031-deploy-azure.yml` (environment: `dev`)
- [ ] Watch Terraform plan output — confirm only `create` actions (no orphaned state)
- [ ] Wait for green (~20 min)
- [ ] Copy `frontdoor_endpoint_host_name` from Terraform outputs
- [ ] Update `CNA_NEXTAUTH_URL` GitHub Variable → new Front Door hostname
- [ ] Update Entra ID redirect URI → `https://<new-hostname>/api/auth/callback/microsoft-entra-id`
- [ ] Re-run `031-deploy-azure.yml` to apply the updated NextAuth URL
- [ ] ✅ `KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME` are now set automatically by 031

### 1e. Validate the Live Platform

- [ ] Run `011-sync-keys.yml` → confirm all Key Vault secrets are populated
- [ ] Navigate to Front Door URL → web app loads
- [ ] Sign in with Microsoft Entra → auth flow completes, dashboard loads
- [ ] Create a test engagement → confirm DB write succeeds
- [ ] Add a cloud credential → confirm encryption/decryption works
- [ ] Run discovery → confirm per-subscription job fires, progress updates
- [ ] Check Application Insights Live Metrics → traffic shows up
- [ ] Generate at least one assessment → confirm AI content is returned and stored
- [ ] Create interactive assessment → confirm AI generation completes (~30–60 sec)
- [ ] Open presentation dashboard → confirm subscription count matches actual subscriptions synced

---

## Beta — Step 2: Beta Validation Checklist

Once the environment is up and smoke-tested, run through these scenarios:

### Discovery

- [ ] Add two or more Azure credentials to a single engagement
- [ ] Run "Re-sync all" → confirm two independent jobs appear (one per credential)
- [ ] Confirm each subscription card has its own progress bar and log
- [ ] Check inventory page → confirm both subscriptions appear merged

### Findings

- [ ] Run AI analysis after discovery → confirm findings are stored
- [ ] Check findings page header: unique-issue count should differ from raw total
- [ ] Apply severity filter → confirm "Showing X of Y issues (Z of N findings)" label updates

### Deliverables

- [ ] Generate each of the 5 assessment types individually
- [ ] Generate all assessments at once → confirm 5 deliverables created
- [ ] Open COMPREHENSIVE_ASSESSMENT → confirm it renders as HTML (not Markdown)
- [ ] Delete all deliverables → regenerate → confirm fresh AI content each time

### Interactive Assessment / Presentation

- [ ] Create interactive assessment → button shows "Generating with AI…"
- [ ] After completion, confirm "View Report" (AI HTML) AND "Dashboard" buttons appear
- [ ] Open Dashboard (presentation) → Executive page shows correct subscription count
- [ ] All 5 presentation pages load without errors (overview, executive, technical, compliance, remediation)

### Auth & Roles

- [ ] Sign in as ANALYST → can create/run engagements
- [ ] Confirm REVIEWER role can view but not trigger discovery
- [ ] Confirm CLIENT role reaches deliverables portal only

---

## ~~Sprint 1 — Beta Hard Blockers~~ ✅ CLOSED

~~All items shipped in commit `1907596`.~~

### ~~Code Bugs~~

- [x] ~~**Fix `_collect_private_endpoints()` — PE IPs always empty**~~
  ~~Already implemented — NIC GET calls present at lines 905–918.~~

- [x] ~~**Fix `vpn_client_pools` list-of-lists bug**~~
  ~~Already implemented — line 819 uses `.extend()`.~~

- [x] ~~**Wire `azure_network.py` and `azure_security.py` stubs**~~
  ~~Both now raise `NotImplementedError` with a clear user-facing message.~~

### ~~Schema & Analysis Gaps~~

- [x] ~~**Implement `_classify_subnet()` helper in `azure_discovery.py`**~~
  ~~Module-level helper added. `SubnetType` (`public` | `private` | `isolated` | `unknown`) now populated on every `AzureSubnet` at discovery time.~~

- [x] ~~**Implement peering firewall-bypass check (`AZ-NET-012`) in `analysis_engine.py`**~~
  ~~Fires on spoke subnets with no UDR, or a UDR missing `0.0.0.0/0 → VirtualAppliance`.~~

- [x] ~~**Add firewall diagnostic settings check (`AZ-NET-013`) in `analysis_engine.py`**~~
  ~~`_collect_observability()` queries ARM diagnostic settings per firewall. AZ-NET-013 fires when any firewall lacks a Log Analytics sink.~~

### ~~CI/CD & Supply Chain~~

- [x] ~~**Auto-write Terraform outputs to GitHub Variables in `031-deploy-azure.yml`**~~
  ~~Step "Update GitHub Variables from Terraform outputs" runs after `terraform apply`.~~

- [x] ~~**Add `CNA_MCP_SERVER_URL` to `secrets-reference.md` and `.env.example`**~~
  ~~`CNA_MCP_SERVER_URL=none` documented as default fallback in both files.~~

---

## ~~Sprint 2 — East-West Visibility~~ ✅ CLOSED

### ~~New Metrics Collectors~~

- [x] ~~**Collect Azure Firewall metrics** — `DataProcessed`, `ApplicationRuleHit`, `NetworkRuleHit`, `NatRuleHit`~~
  ~~Rule `AZ-NET-009`: firewall present with 0 rule hits = misconfigured or bypassed.~~

- [x] ~~**Collect Load Balancer SNAT metrics** — `SnatConnectionCount`, `UsedSnatPorts`, `AllocatedSnatPorts`~~
  ~~Rule `AZ-NET-010`: `UsedSnatPorts / AllocatedSnatPorts > 80%` = SNAT exhaustion risk.~~

- [x] ~~**Collect gateway `AverageBandwidth` metric** → populates `GatewayMetric.utilization_pct`~~
  ~~Rule `AZ-NET-008`: `utilization_pct > 80%` = gateway saturation.~~

- [x] ~~**Compute VNet IP space utilization %** from existing subnet CIDR data~~
  ~~Rule `AZ-NET-011`: `vnet_utilization > 85%` = IP exhaustion risk.~~

- [x] ~~**Collect ER circuit utilization** — `BitsInPerSecond`, `BitsOutPerSecond` on ER circuit resources~~
  ~~Rule `AZ-NET-016`: `primary_utilization_pct > 80%` = circuit saturation risk.~~

- [x] ~~**Collect DDoS attack telemetry** — `IfUnderDDoSAttack`, `DdosPacketsDropped` on Public IPs~~
  ~~Rule `AZ-NET-017` (CRITICAL): active attack detected in last 24h.~~

- [x] ~~**Add Cost Management API call** (billing-derived throughput proxy)~~
  ~~`azure-mgmt-costmanagement` queries `Microsoft.Network` + `Bandwidth` meter categories MTD. `NetworkMetrics.egress_cost_usd_mtd` populated. Requires Billing Reader.~~

- [x] ~~**Add NTA east-west / north-south bytes** via Log Analytics `AzureNetworkAnalytics_CL`~~
  ~~`NetworkMetrics.nta_east_west_bytes_24h` / `nta_north_south_bytes_24h` populated. Requires Traffic Analytics enabled on NSG flow logs.~~

### ~~Observability Gaps~~

- [x] ~~**Add Traffic Analytics state** to `ObservabilityData`~~
  ~~Rule `AZ-NET-014`: flow log enabled but Traffic Analytics disabled.~~

- [x] ~~**Add Bastion diagnostic settings check**~~
  ~~`_collect_observability()` queries ARM diagnostic settings per Bastion host. Rule `AZ-NET-015`: Bastion without session audit logs.~~

### ~~Compliance Mappings~~

- [x] ~~**Add PCI-DSS 4.0 `framework_mappings`** to AZ-NET-001/002/003/004/007~~

- [x] ~~**Add ISO 27001:2022 A.8.20–A.8.23 mappings** to network findings~~

- [x] ~~**Add HIPAA § 164.312 framework mappings** to AZ-NET-001/002/003/004/006/007/017~~

- [x] ~~**Add FedRAMP Moderate framework mappings** to AZ-NET-001/002/003/004/005/006/007/016/017/018~~

---

## ~~Sprint 3 — Production Hardening~~ ✅ CLOSED

- [x] ~~**Pin `node:20-alpine` to SHA digest** in `cna-web/Dockerfile`~~
  ~~All 4 `FROM` stages pinned to `sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293`.~~

- [x] ~~**Pin `gitleaks-action` to SHA** in `020-test-codebase.yml`~~
  ~~Pinned to `ff98106e4c7b2bc287b24eaf42907196329070c7` (v2 SHA as of 2026-04-17).~~

- [x] ~~**Verify `infra/terraform/environments/azure/prod/` mirrors `dev/`**~~
  ~~Diff obtained — prod intentionally differs (ZRS, 90d retention, no scale-to-zero). Prod missing `AZURE_STORAGE_ACCOUNT_NAME` / `AZURE_STORAGE_CONTAINER_ENGAGEMENTS` — must document before first prod run.~~

- [x] ~~**Add Front Door WAF policy discovery** to `azure_discovery.py`~~
  ~~`_collect_front_door_waf_policies()` implemented. Rule `AZ-NET-018`: WAF in Detection mode.~~

---

## ~~Sprint 4 — Assessment Completeness~~ ✅ CLOSED

- [x] ~~**Implement AZ-NET-005 emission logic** — peering `allow_gateway_transit` without local gateway~~

- [x] ~~**Implement AZ-NET-006 emission logic** — VNet with no NSG flow logs enabled~~

- [x] ~~**Add PE DNS resolution validation** — `_collect_private_endpoints()` now validates FQDNs~~
  ~~Uses Python `socket.gethostbyname()` + RFC 1918 range check. Populates `dns_resolves_to_private_ip`.~~

---

## Sprint 5 — WCAG 2.1 / W3C / OWASP Audit

> **Full audit report:** `sprint5-audit-report.html` at project root (47 findings: 5 CRITICAL · 18 HIGH · 21 MEDIUM · 8 LOW)
> **To generate PDF:** Open `sprint5-audit-report.html` in Chrome/Edge → File → Print → "Save as PDF" → Destination: Save as PDF

### 🔴 #1 PRIORITY — Generate & Distribute Audit PDF

- [x] **[SPRINT5-PDF] Open audit report and save as PDF for distribution**
  File: `sprint5-audit-report.html` (project root)
  Steps: Open in Chrome/Edge → Ctrl+P → Change destination to "Save as PDF" → Save
  Distribute to: Engineering lead, security reviewer, accessibility lead
  Filename convention: `CBTS-CNA-Sprint5-Audit-YYYYMMDD.pdf`

- [x] **[SPRINT5-PDF] Commit the HTML audit report to source control**
  The report lives at project root as `sprint5-audit-report.html`.
  Commit message: `docs: add Sprint 5 WCAG/W3C/OWASP audit report (47 findings)`

- [ ] **[SPRINT5-TRACK] Create GitHub Issues for all Wave 1 CRITICAL findings**
  Create one issue per finding (OWA-01, OWA-07, WAI-01, WAI-02, WAI-03, WAI-04, WAI-05).
  Label: `sprint-5`, `accessibility` or `security`, priority: `P0`

---

### Wave 1 — CRITICAL (Accessibility + Security Hard Blockers)

- [x] **[OWA-01] Implement nonce-based CSP** — replace `unsafe-inline` in `script-src` with `'nonce-{NONCE}'`
  Next.js 15 supports nonce via middleware. Required for OWASP A05 / ASVS 14.4.6 compliance.
  File: `apps/cna-web/next.config.ts` L23

- [x] **[WAI-03] Replace `sp-help-modal.tsx` with accessible `<dialog>` element**
  Current modal has no `role="dialog"`, no focus trap, no Escape key handler, and no `aria-modal`.
  Fix: use native `<dialog>` element or `@radix-ui/react-dialog` primitive.
  File: `apps/cna-web/components/ui/sp-help-modal.tsx`

- [x] **[WAI-01] Add `aria-hidden` / `aria-label` to all navigation SVG icons**
  All `NAV_ITEMS` SVGs lack `aria-hidden="true"`. In collapsed mode, icons are the only content.
  File: `apps/cna-web/components/ui/engagement-sidebar.tsx`

- [x] **[WAI-02] Replace `title` attribute with `aria-label` on sidebar toggle button**
  Add `aria-label`, `aria-expanded`, `aria-controls` to the collapse/expand button.
  File: `apps/cna-web/components/ui/engagement-sidebar.tsx` L145–163

- [x] **[WAI-04] Add `aria-expanded` + `aria-controls` to `InstanceRow` buttons in findings**
  Expand/collapse state is visual-only; screen readers cannot detect it.
  File: `apps/cna-web/app/(dashboard)/engagements/[id]/findings/findings-client.tsx` L83–102

- [x] **[WAI-05] Add `aria-controls` (with matching `id`) to group header buttons in findings**
  `aria-expanded` exists but `aria-controls` is missing — panel cannot be programmatically associated.
  File: `apps/cna-web/app/(dashboard)/engagements/[id]/findings/findings-client.tsx` L428–434

- [x] **[OWA-07] Validate `customerLogoUrl` server-side — SSRF risk**
  URL is taken verbatim from form data and passed to AI generation. Add domain allowlist.
  File: `apps/cna-web/app/(dashboard)/engagements/[id]/deliverables/actions.ts` L93

### Wave 2 — HIGH (Required for WCAG AA Conformance + OWASP Rating)

- [x] **[WAI-06] Replace label-caps `<p>` elements with semantic heading elements**
  Section labels like "Engagement Progress", "Jump to", "Generate Assessment" must be `<h2>`/`<h3>`.
  Files: `page.tsx`, `deliverables/page.tsx`, and all pages with `.label-caps` labels

- [x] **[WAI-07] Fix risk matrix table — add `<caption>`, `scope="col"`, `scope="row"`**
  File: `findings-client.tsx` L293–333

- [x] **[WAI-08] Add `aria-pressed` / `aria-checked` to severity filter toggle buttons**
  Add non-colour active state indicator (border/underline/icon).
  File: `findings-client.tsx` L342–368

- [x] **[WAI-09] Fix colour contrast for `text-navy-400` on light and dark backgrounds**
  `navy-400` on white ≈ 3.2:1 (fails AA 4.5:1). Adjust token or use higher-contrast alias.
  File: `globals.css`, all components using `text-navy-400`

- [x] **[WAI-10] Add global `focus-visible` styles to `globals.css`**
  No global focus indicator. All interactive elements missing visible keyboard focus ring.
  File: `apps/cna-web/app/globals.css`, `btn-teal`, sidebar links

- [x] **[WAI-11] Add `role="progressbar"` and `aria-valuenow` to discovery progress bar**
  File: `connections-panel.tsx` L479–484

- [x] **[WAI-13] Add `aria-label` to severity bar segments in findings summary**
  Proportional severity bar conveys information through colour only.
  File: `findings-client.tsx` L273–282

- [x] **[WAI-16] Add skip-to-main-content link at top of dashboard layout**
  File: `apps/cna-web/app/(dashboard)/layout.tsx`

- [x] **[WAI-19] Add `aria-hidden="true"` to spinner SVGs; add `sr-only` live region**
  Files: `submit-button.tsx`, `connections-panel.tsx`

- [x] **[W3C-01] Replace `<img>` logo elements with `next/image` in dashboard header**
  Eliminates CLS and removes `eslint-disable` suppression.
  File: `apps/cna-web/app/(dashboard)/layout.tsx` L24–33

- [x] **[W3C-02] Add `aria-hidden="true" focusable="false"` to all decorative inline SVGs**
  Affects all components. Consider creating a shared `<Icon>` wrapper component.

- [x] **[W3C-03] Add W3C standard scrollbar CSS alongside webkit vendor prefix**
  Add `scrollbar-width: thin; scrollbar-color: var(--accent) transparent;` to `globals.css`.

- [x] **[W3C-04] Remove or scope `-webkit-font-smoothing: antialiased`**
  Disables ClearType on Windows — degrades readability for Windows users.
  File: `apps/cna-web/app/globals.css` L84–86

- [x] **[OWA-02] Add per-user rate limiting to Server Actions (AI generation, discovery start)**
  Implement with `@upstash/ratelimit` or similar. 5 requests per 60s per user per action.
  Files: `deliverables/actions.ts`, `discovery/actions.ts`

- [x] **[OWA-03] Fix CSRF protection on `deleteEngagement` — wrap in `<form>` element**
  File: `apps/cna-web/components/ui/delete-engagement-button.tsx` L28–30

- [x] **[OWA-04] Restrict non-Secure session cookie fallback to `NODE_ENV !== 'production'`**
  File: `apps/cna-web/middleware.ts` L19–21

- [x] **[OWA-05] Return 401 before DB lookup in discovery-jobs API route**
  Prevents job ID enumeration via timing side channel.
  File: `apps/cna-web/app/api/discovery-jobs/[jobId]/route.ts`

### Wave 3 — MEDIUM (Best Practice / Defence-in-Depth)

- [x] **[OWA-08] Audit `lib/auth.ts` — enforce `useSecureCookies: true` unconditionally in prod**

- [x] **[OWA-09] Replace `confirm()` dialogs with accessible modal confirmation components**
  Files: `delete-engagement-button.tsx`, any other uses of `window.confirm()`

- [x] **[OWA-10] Add Zod validation to `progressLog` JSON parse in `connections-panel.tsx`**
  File: `connections-panel.tsx` L90–96

- [x] **[OWA-12] Map raw Azure SDK errors to user-friendly messages in `deliverables/actions.ts`**
  Do not return raw error strings containing Azure resource names to the browser.

- [x] **[OWA-13] Expand `Permissions-Policy` header with all modern browser APIs**
  Add: `payment=()`, `usb=()`, `serial=()`, `hid=()`, `bluetooth=()`, `display-capture=()`
  File: `next.config.ts` L14

- [x] **[OWA-14] Add `preload` directive to `Strict-Transport-Security` header**
  File: `next.config.ts` L10

- [x] **[OWA-06] Add server-side MIME / magic-byte validation to document upload action**
  Allowlist: `application/pdf`, `text/plain`, `image/png`, `image/jpeg`.

- [x] **[WAI-12] Fix `<details>/<summary>` accessibility for Firefox+NVDA compatibility**
  Add `aria-expanded` explicitly or revert to button-based expand pattern.
  File: `connections-panel.tsx` L491–525

- [x] **[WAI-14] Add "(opens in new tab)" `sr-only` text to all `target="_blank"` links**
  Files: `sp-help-modal.tsx`, `findings-client.tsx`

- [x] **[WAI-17] Add `aria-label` to `<aside>` and `<nav>` landmark elements in sidebar**
  File: `engagement-sidebar.tsx`

- [x] **[WAI-20] Add `autocomplete` attributes to credential and engagement form inputs**
  Sensitive fields: `autocomplete="off"`. Non-sensitive: use SC 1.3.5 tokens.

- [x] **[WAI-21] Increase `focus:ring-1` to `focus:ring-2` on `<select>` elements**
  File: `findings-client.tsx` L373–393

- [x] **[WAI-23] Add `aria-label` and `aria-current="step"` to phase stepper steps**
  File: `apps/cna-web/app/(dashboard)/engagements/[id]/page.tsx` L82–128

- [x] **[W3C-05] Add `<meta name="color-scheme" content="light dark">` to root layout**
  Prevents white flash on dark mode load and fixes form control colours.
  File: `apps/cna-web/app/layout.tsx`

- [x] **[W3C-06] Add `@supports (backdrop-filter: blur(1px))` feature query to `.glass` class**
  Provides proper opaque fallback for Firefox.
  File: `globals.css`

- [x] **[W3C-08] Add CSS custom property type declarations for `--bar-pct`**
  Replace `as React.CSSProperties` cast with a typed module augmentation.
  File: `apps/cna-web/types/css.d.ts` (new)

- [x] **[W3C-09] Update `rel="noreferrer"` to `rel="noopener noreferrer"` on deliverable links**
  File: `deliverables/page.tsx` L183

- [x] **[W3C-10] Add `aria-label` to all per-deliverable delete `<form>` elements**
  Prevents screen readers announcing identical "delete" forms.
  File: `deliverables/page.tsx` L196–208

- [x] **[W3C-12] Replace dual `<img>` logo pattern with `<picture>` element**
  Eliminates duplicate image requests and duplicate `alt` announcements.
  File: `apps/cna-web/app/(dashboard)/layout.tsx` L24–33

---

## Post-Beta Roadmap

| Item | Priority | Notes |
| --- | --- | --- |
| Production deployment | **High** | Run `031` targeting `prod` after dev Beta validation. Prod env var gap fixed in `2e243ea`. |
| ~~AWS Provider Expansion (Phase G)~~ | ~~High~~ | ✅ Done — AWS Network Firewall + WAF v2 collectors added; AWS-NET-012/013 rules live |
| ~~Phase C: Azure network/security discovery stubs~~ | ~~Medium~~ | ✅ Done — `azure_network.py` and `azure_security.py` now re-export from `azure_discovery.py` |
| ~~Client portal hardening~~ | ~~Medium~~ | ✅ Done — `deleteBlob()`, `generateSasUrl()`, `cleanupExpiredDeliverables()` implemented |
| ~~App Gateway capacity metrics~~ | ~~Low~~ | ✅ Done — collector #9 in `_collect_network_metrics`; AZ-NET-019 rule live |
| ~~Defender for Cloud network recommendations~~ | ~~Low~~ | ✅ Done — `_collect_defender_assessments()` + `defender_assessments` on topology |
| ~~CISA ZTMM v2 framework mappings~~ | ~~Low~~ | ✅ Done — all 30 rule emissions include CISA ZTMM v2 pillar/control mappings |
| MCP integration | **High** | Wire live MCP endpoints (e.g. `cna/modules/*/module.yaml`) to background worker and AI engine |
| Draw.io integration | **Medium** | Build diagram export to `.drawio` XML format for custom user editing |
| AWS assessment | **Medium** | Support AWS network and security assessments with custom finding rules |
| UI Update for new badging | **Low** | Refresh frontend elements with status badges (compliant, warning, error, etc.) |
| Replatform to AWS | **High** | Migrate Next.js frontend, FastAPI backend, and DB resources to AWS (ECS, RDS, CloudFront) |
| JA (Japanese) language toggle | Low | `ja_review_complete` flag — requires translated glossary review |
| Pre-commit hook enforcement monitoring | Ongoing | `detect-secrets` + `gitleaks` — monitor for false positives |

---

## Current Azure Rule Coverage

| Rule ID | Name | Severity | Status |
| --- | --- | --- | --- |
| AZ-NET-001 | VNet no DDoS protection | LOW | ✅ Live |
| AZ-NET-002 | Subnet no NSG | HIGH | ✅ Live |
| AZ-NET-003 | Firewall threat intel not Deny | CRITICAL | ✅ Live |
| AZ-NET-004 | ExpressRoute no redundancy | LOW | ✅ Live |
| AZ-NET-005 | Peering allow gateway transit (no local GW) | LOW | ✅ Live |
| AZ-NET-006 | VNet no flow logs | HIGH | ✅ Live |
| AZ-NET-007 | App Gateway WAF disabled | HIGH | ✅ Live |
| AZ-NET-008 | Gateway saturation >80% | HIGH | ✅ Live |
| AZ-NET-009 | Firewall 0 rule hits | HIGH | ✅ Live |
| AZ-NET-010 | LB SNAT exhaustion >80% | HIGH | ✅ Live |
| AZ-NET-011 | VNet IP space >85% full | HIGH | ✅ Live |
| AZ-NET-012 | Peering firewall bypass | MEDIUM | ✅ Live |
| AZ-NET-013 | Firewall no diagnostics | MEDIUM | ✅ Live |
| AZ-NET-014 | Traffic Analytics disabled | MEDIUM | ✅ Live |
| AZ-NET-015 | Bastion no session logs | MEDIUM | ✅ Live |
| AZ-NET-016 | ER circuit saturation >80% | HIGH | ✅ Live |
| AZ-NET-017 | DDoS attack detected | CRITICAL | ✅ Live |
| AZ-NET-018 | Front Door WAF in Detection mode | MEDIUM | ✅ Live |
| AZ-NET-019 | App Gateway high latency / failure rate | HIGH | ✅ Live |

**19 of 19 Azure rules active.**

## Current AWS Rule Coverage

| Rule ID | Name | Severity | Status |
| --- | --- | --- | --- |
| AWS-NET-001 | SG unrestricted SSH | CRITICAL | ✅ Live |
| AWS-NET-002 | SG unrestricted RDP | CRITICAL | ✅ Live |
| AWS-NET-003 | SG unrestricted all traffic | CRITICAL | ✅ Live |
| AWS-NET-004 | VPC flow logs disabled | HIGH | ✅ Live |
| AWS-NET-005–011 | (existing rules) | various | ✅ Live |
| AWS-NET-012 | No Network Firewall in VPC with IGW | LOW | ✅ Live |
| AWS-NET-013 | WAF Web ACL not associated with any resource | MEDIUM | ✅ Live |

**All AWS rules active.**

---

## Useful Reference

| Document | Path |
| --- | --- |
| Phase sign-offs | `documentation/phase-reviews/phase-critiques-and-sign-offs.md` |
| Naming conventions | `documentation/architecture/40-naming-conventions.md` |
| Azure infra reference | `documentation/architecture/38-azure-infra-deployment-reference.md` |
| Platform architecture | `documentation/architecture/39-platform-architecture-revised.md` |
| Deployment guide | `documentation/deployment-guide.md` |
| Secrets reference | `documentation/secrets-reference.md` |
| Workflows guide | `documentation/workflows-guide.md` |

---

## Dependency Hygiene Backlog (added 2026-04-28)

| Item | Priority | Notes |
| --- | --- | --- |
| Upgrade `next-auth` from `5.0.0-beta.30` to stable v5 when released | HIGH | No stable v5 exists as of 2026-04-28. Track [nextauthjs/next-auth releases](https://github.com/nextauthjs/next-auth/releases). |
| Merge 6 open Dependabot PRs (#13–#18) | HIGH | rich, n2g, tenacity, boto3, ruff, python base image updates |
| Evaluate whether `openai>=1.50` (Python) and `openai: ^6.34.0` (Node) can be aligned | LOW | Different major versions reflect API SDK generations; document intentionally. |
| Implement nonce-based CSP for Next.js scripts | MEDIUM | Current `unsafe-inline` is a temporary workaround for Tailwind; see next.config.ts. |
