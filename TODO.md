# CNA Platform — Active TODO

> **Status as of 2026-04-17**
> Alpha stage is complete and closed. All six delivery phases (A–F) are signed off.
> The dev environment is being torn down and redeployed clean as the Alpha→Beta transition.
> This file tracks the Beta deployment checklist and post-Beta roadmap.

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
| `APPLICATION_INSIGHTS_NAME` | Reset to `none` — will be recreated by Terraform |
| `KEY_VAULT_NAME` | Reset to `none` — will be recreated by Terraform |

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
- [ ] Update `KEY_VAULT_NAME` and `APPLICATION_INSIGHTS_NAME` variables from outputs

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

## Sprint 1 — Beta Hard Blockers (Do Before First Paid Run)

Derived from senior architect review (2026-04-17). These are bugs or silent failures
that will produce incorrect or empty data in a live assessment.

### Code Bugs

- [x] **Fix `_collect_private_endpoints()` — PE IPs always empty**  
  Already implemented — NIC GET calls present at lines 905–918.

- [x] **Fix `vpn_client_pools` list-of-lists bug**  
  Already implemented — line 819 uses `.extend()`.

- [x] **Wire `azure_network.py` and `azure_security.py` stubs**  
  Both now raise `NotImplementedError` with a clear user-facing message.

### Schema & Analysis Gaps

- [x] **Implement `_classify_subnet()` helper in `azure_discovery.py`**  
  Added module-level `_classify_subnet()`. `SubnetType` now populated on every subnet.  
  Categories: `public` | `private` | `isolated` | `unknown`.

- [x] **Implement peering firewall-bypass check (`AZ-NET-012`) in `analysis_engine.py`**  
  Fires on spoke subnets with no route table, or a route table missing `0.0.0.0/0 → VirtualAppliance`.

- [x] **Add firewall diagnostic settings check (`AZ-NET-013`) in `analysis_engine.py`**  
  `_collect_observability()` now queries ARM diagnostic settings per firewall.  
  `ObservabilityData.firewalls_with_diagnostics` / `firewalls_total` populated.  
  AZ-NET-013 fires when `firewalls_total > firewalls_with_diagnostics`.

### CI/CD & Supply Chain

- [x] **Auto-write Terraform outputs to GitHub Variables in `031-deploy-azure.yml`**  
  Step "Update GitHub Variables from Terraform outputs" added after `terraform apply`.

- [x] **Add `CNA_MCP_SERVER_URL` to `secrets-reference.md` and `.env.example`**  
  Added as `CNA_MCP_SERVER_URL=none` (default fallback). Both docs updated.

---

## Sprint 2 — East-West Visibility (Before First Paid Client)

Derived from assessment gap analysis. See `beta_readiness_and_assessment_gap_analysis.md`.
The East-West section of a 10-page assessment is currently config-only (45% complete).
These items add real traffic telemetry.

### New Metrics Collectors (in `azure_discovery.py`)

- [x] **Collect Azure Firewall metrics** — `DataProcessed`, `ApplicationRuleHit`, `NetworkRuleHit`, `NatRuleHit`  
  Add `_collect_firewall_metrics()` method. New `FirewallMetric` model in `topology_schema.py`.
  New rule `AZ-NET-009`: firewall present with 0 rule hits = misconfigured or bypassed.

- [x] **Collect Load Balancer SNAT metrics** — `SnatConnectionCount`, `UsedSnatPorts`, `AllocatedSnatPorts`  
  Add `_collect_lb_metrics()` method. New `LoadBalancerMetric` model in `topology_schema.py`.
  New rule `AZ-NET-010`: `UsedSnatPorts / AllocatedSnatPorts > 80%` = SNAT exhaustion risk.

- [x] **Collect gateway `AverageBandwidth` metric** to populate `GatewayMetric.utilization_pct`  
  Field already exists in schema — collector never queries it.  
  New rule `AZ-NET-008`: `utilization_pct > 80%` = gateway saturation.

- [x] **Compute VNet IP space utilization %** from existing subnet CIDR data  
  No new API call needed — calculate `sum(subnet CIDRs) / VNet CIDR * 100`.  
  New rule `AZ-NET-011`: `vnet_utilization > 85%` = IP exhaustion risk.

### Observability Gaps (in `azure_discovery.py`)

- [x] **Add Traffic Analytics state** to `ObservabilityData`  
  Extend NSG flow log enumeration to read `traffic_analytics_configuration.enabled`
  and `traffic_analytics_configuration.workspace_id` per flow log resource.  
  New rule `AZ-NET-014`: flow log enabled but Traffic Analytics disabled.

- [x] **Add Bastion diagnostic settings check**  
  `_collect_observability()` queries ARM diagnostic settings per Bastion host.  
  `ObservabilityData.bastion_with_diagnostics` / `bastion_total` populated.  
  New rule `AZ-NET-015`: Bastion without session logs.

- [ ] **Add Cost Management API call** (billing-derived throughput proxy)  
  Use `azure-mgmt-costmanagement` to query `Microsoft.Network` meter category MTD.  
  Correlate `Inter-VNet Data Transfer` spend to approximate east-west byte volume.  
  No Monitor permissions required — works with Billing Reader.

### Compliance Mappings

- [x] **Add PCI-DSS 4.0 `framework_mappings`** to existing rules `AZ-NET-001` through `AZ-NET-007`  
  Req 1.2 → segmentation (AZ-NET-002), Req 1.3 → inbound/outbound (AZ-NET-003, 007).

- [x] **Add ISO 27001:2022 A.8.20–A.8.23 mappings** to network findings  
  A.8.20 (AZ-NET-001, 003), A.8.21 (AZ-NET-004), A.8.22 (AZ-NET-002), A.8.23 (AZ-NET-007).

---

## Sprint 3 — Production Hardening

- [ ] **Pin `node:20-alpine` to SHA digest** in `cna-web/Dockerfile`  
  Run `docker pull node:20-alpine --platform linux/amd64` to get current digest.  
  Update: `FROM node:20-alpine@sha256:<hash>`.

- [x] **Pin `gitleaks-action` to SHA** in `020-test-codebase.yml`  
  Pinned to `ff98106e4c7b2bc287b24eaf42907196329070c7` (v2 current commit SHA as of 2026-04-17).

- [ ] **Verify `infra/terraform/environments/azure/prod/` mirrors `dev/`**  
  Run `diff infra/terraform/environments/azure/dev/ infra/terraform/environments/azure/prod/` before prod promote.

- [ ] **Add `Front Door WAF policy` discovery** to `azure_discovery.py`  
  Permission: `Microsoft.Network/frontDoorWebApplicationFirewallPolicies/read`.  
  Required to cover customer-tenant Front Door WAF — currently CNA only assesses App GW WAF.

---

## Post-Beta Roadmap

| Item | Priority | Notes |
| --- | --- | --- |
| Production deployment | High | Run `031` targeting `prod` after dev Beta validation |
| AWS Provider Expansion (Phase G) | High | Azure parity; needs Phase C discovery stubs for AWS |
| Phase C: Azure network/security discovery stubs | Medium | `azure_network/security` module stubs — remaining Phase C work |
| JA (Japanese) language toggle | Low | `ja_review_complete` flag — requires translated glossary review |
| MCP server wiring | Low | `cna/modules/*/module.yaml` specifies servers — needs live MCP endpoints |
| Client portal hardening | Medium | Retention engine (90 days), SAS token TTL enforcement |
| Pre-commit hook enforcement monitoring | Ongoing | `detect-secrets` + `gitleaks` — monitor for false positives |
| Node.js Dockerfile base image SHA pin | Low | Moved to Sprint 3 above |
| gitleaks-action SHA pin in `020-test-codebase.yml` | Low | Moved to Sprint 3 above |

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
