# CNA Platform — Active TODO

> **Status as of 2026-04-17 · commit `1907596`**
> Alpha stage is complete and closed. All six delivery phases (A–F) are signed off.
> Sprint 1 (Beta Hard Blockers) and most of Sprint 2 (East-West Visibility) are now closed.
> Beta deployment sequence is ready to run. Sprint 3 and Post-Beta items remain.

---

## Alpha Completed (2026-04-14)

Everything below shipped and is live on the dev environment at SHA `ace931c`.

| Feature | Status |
| --- | --- |
| Platform architecture (3-container, PostgreSQL, Entra ID) | ✅ Done |
| Terraform modules (all Azure resources) | ✅ Done |
| GitHub Actions workflows (000–031) | ✅ Done |
| Entra ID auth + OIDC federation | ✅ Done |
| First Terraform deployment (dev) | ✅ Done |
| Per-subscription sync groups (one `DiscoveryJob` per credential) | ✅ Done |
| Multi-subscription topology merge (inventory + presentations + deliverables) | ✅ Done |
| Findings count — unique issue groups vs. raw count | ✅ Done |
| Five assessment types (COMPREHENSIVE HTML + 4 Markdown) | ✅ Done |
| Comprehensive Assessment HTML output (fixed system prompt conflict) | ✅ Done |
| MS Learn enrichment (live fetch at generation time) | ✅ Done |
| Interactive Assessment: AI generation on every create/recreate | ✅ Done |
| Interactive Assessment: "View Report" + "Dashboard" split in portal | ✅ Done |
| Presentation dashboard: all pages use merged topology (fixes "1 subscription") | ✅ Done |
| Error surfacing in create-assessment-button | ✅ Done |

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

## Sprint 1 — Beta Hard Blockers ✅ CLOSED

All items shipped in commit `1907596`.

### Code Bugs

- [x] **Fix `_collect_private_endpoints()` — PE IPs always empty**
  Already implemented — NIC GET calls present at lines 905–918.

- [x] **Fix `vpn_client_pools` list-of-lists bug**
  Already implemented — line 819 uses `.extend()`.

- [x] **Wire `azure_network.py` and `azure_security.py` stubs**
  Both now raise `NotImplementedError` with a clear user-facing message.

### Schema & Analysis Gaps

- [x] **Implement `_classify_subnet()` helper in `azure_discovery.py`**
  Module-level helper added. `SubnetType` (`public` | `private` | `isolated` | `unknown`) now
  populated on every `AzureSubnet` at discovery time.

- [x] **Implement peering firewall-bypass check (`AZ-NET-012`) in `analysis_engine.py`**
  Fires on spoke subnets with no UDR, or a UDR missing `0.0.0.0/0 → VirtualAppliance`.

- [x] **Add firewall diagnostic settings check (`AZ-NET-013`) in `analysis_engine.py`**
  `_collect_observability()` queries ARM diagnostic settings per firewall.
  `ObservabilityData.firewalls_with_diagnostics / firewalls_total` populated.
  AZ-NET-013 fires when any firewall lacks a Log Analytics sink.

### CI/CD & Supply Chain

- [x] **Auto-write Terraform outputs to GitHub Variables in `031-deploy-azure.yml`**
  Step "Update GitHub Variables from Terraform outputs" runs after `terraform apply`.

- [x] **Add `CNA_MCP_SERVER_URL` to `secrets-reference.md` and `.env.example`**
  `CNA_MCP_SERVER_URL=none` documented as default fallback in both files.

---

## Sprint 2 — East-West Visibility ✅ MOSTLY CLOSED

All metrics collectors and new analysis rules shipped. One item remains.

### New Metrics Collectors ✅

- [x] **Collect Azure Firewall metrics** — `DataProcessed`, `ApplicationRuleHit`, `NetworkRuleHit`, `NatRuleHit`
  Rule `AZ-NET-009`: firewall present with 0 rule hits = misconfigured or bypassed.

- [x] **Collect Load Balancer SNAT metrics** — `SnatConnectionCount`, `UsedSnatPorts`, `AllocatedSnatPorts`
  Rule `AZ-NET-010`: `UsedSnatPorts / AllocatedSnatPorts > 80%` = SNAT exhaustion risk.

- [x] **Collect gateway `AverageBandwidth` metric** → populates `GatewayMetric.utilization_pct`
  Rule `AZ-NET-008`: `utilization_pct > 80%` = gateway saturation.

- [x] **Compute VNet IP space utilization %** from existing subnet CIDR data
  Rule `AZ-NET-011`: `vnet_utilization > 85%` = IP exhaustion risk.

### Observability Gaps ✅

- [x] **Add Traffic Analytics state** to `ObservabilityData`
  Rule `AZ-NET-014`: flow log enabled but Traffic Analytics disabled.

- [x] **Add Bastion diagnostic settings check**
  `_collect_observability()` queries ARM diagnostic settings per Bastion host.
  `ObservabilityData.bastion_with_diagnostics / bastion_total` populated.
  Rule `AZ-NET-015`: Bastion without session audit logs.

- [ ] **Add Cost Management API call** (billing-derived throughput proxy)
  Use `azure-mgmt-costmanagement` to query `Microsoft.Network` meter category MTD.
  Correlate `Inter-VNet Data Transfer` spend to approximate east-west byte volume.
  No Azure Monitor permissions required — works with Billing Reader.
  `NetworkMetrics.egress_cost_usd_mtd` field already exists in schema.

### Compliance Mappings ✅

- [x] **Add PCI-DSS 4.0 `framework_mappings`** to AZ-NET-001/002/003/004/007
  Req 1.2 → segmentation (AZ-NET-002), Req 1.3 → inbound/outbound (AZ-NET-003, 007).

- [x] **Add ISO 27001:2022 A.8.20–A.8.23 mappings** to network findings
  A.8.20 (AZ-NET-001, 003), A.8.21 (AZ-NET-004), A.8.22 (AZ-NET-002), A.8.23 (AZ-NET-007).

---

## Sprint 3 — Production Hardening

- [ ] **Pin `node:20-alpine` to SHA digest** in `cna-web/Dockerfile`
  Run `docker pull node:20-alpine --platform linux/amd64` to capture current digest.
  Update: `FROM node:20-alpine@sha256:<hash>`.

- [x] **Pin `gitleaks-action` to SHA** in `020-test-codebase.yml`
  Pinned to `ff98106e4c7b2bc287b24eaf42907196329070c7` (v2 SHA as of 2026-04-17).

- [ ] **Verify `infra/terraform/environments/azure/prod/` mirrors `dev/`**
  Run `diff infra/terraform/environments/azure/dev/ infra/terraform/environments/azure/prod/`
  before promoting to prod. Failure to do this risks silent config drift.

- [ ] **Add Front Door WAF policy discovery** to `azure_discovery.py`
  Permission: `Microsoft.Network/frontDoorWebApplicationFirewallPolicies/read`.
  Covers customer-tenant Front Door WAF — currently only App GW WAF is assessed.

---

## Post-Beta Roadmap

| Item | Priority | Notes |
| --- | --- | --- |
| Production deployment | High | Run `031` targeting `prod` after dev Beta validation |
| AWS Provider Expansion (Phase G) | High | Azure parity; needs Phase C discovery stubs for AWS |
| NSG flow log analytics query (east-west byte counts) | High | `AzureNetworkAnalytics_CL` Log Analytics query — only remaining east-west telemetry gap |
| ER circuit utilization (`PrimaryBitsInPerSecond`) | Medium | Last gap for Page 6 (Hybrid/WAN) — confirms ER isn't saturated |
| DDoS attack telemetry | Medium | `IfUnderDDoSAttack`, `DdosPacketsDropped` on Public IP resources |
| HIPAA § 164.312 framework mappings | Medium | Healthcare clients — additive to existing rules |
| FedRAMP Moderate mappings (AC-17, SC-7, SI-4) | Medium | Federal/DoD clients — additive to existing rules |
| Phase C: Azure network/security discovery stubs | Medium | `azure_network/security` Phase C — currently raise NotImplementedError |
| Client portal hardening | Medium | Retention engine (90 days), SAS token TTL enforcement |
| JA (Japanese) language toggle | Low | `ja_review_complete` flag — requires translated glossary review |
| MCP server wiring | Low | `cna/modules/*/module.yaml` specifies servers — needs live MCP endpoints |
| Pre-commit hook enforcement monitoring | Ongoing | `detect-secrets` + `gitleaks` — monitor for false positives |

---

## Current Azure Rule Coverage

| Rule ID | Name | Severity | Status |
| --- | --- | --- | --- |
| AZ-NET-001 | VNet no DDoS protection | LOW | ✅ Live |
| AZ-NET-002 | Subnet no NSG | HIGH | ✅ Live |
| AZ-NET-003 | Firewall threat intel not Deny | CRITICAL | ✅ Live |
| AZ-NET-004 | ExpressRoute no redundancy | LOW | ✅ Live |
| AZ-NET-005 | Peering allow gateway transit | LOW | ⚠️ ID declared, no emission logic |
| AZ-NET-006 | VNet no flow logs | HIGH | ⚠️ ID declared, no emission logic |
| AZ-NET-007 | App Gateway WAF disabled | HIGH | ✅ Live |
| AZ-NET-008 | Gateway saturation >80% | HIGH | ✅ Live |
| AZ-NET-009 | Firewall 0 rule hits | HIGH | ✅ Live |
| AZ-NET-010 | LB SNAT exhaustion >80% | HIGH | ✅ Live |
| AZ-NET-011 | VNet IP space >85% full | HIGH | ✅ Live |
| AZ-NET-012 | Peering firewall bypass | MEDIUM | ✅ Live |
| AZ-NET-013 | Firewall no diagnostics | MEDIUM | ✅ Live |
| AZ-NET-014 | Traffic Analytics disabled | MEDIUM | ✅ Live |
| AZ-NET-015 | Bastion no session logs | MEDIUM | ✅ Live |

**13 of 15 rules active.** AZ-NET-005 and AZ-NET-006 need emission logic (Phase C backlog).

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
