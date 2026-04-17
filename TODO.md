# CNA Platform — Active TODO

> **Status as of 2026-04-17 · Session 3 complete**
> Alpha stage is complete and closed. All six delivery phases (A–F) are signed off.
> Sprint 1 (Beta Hard Blockers), Sprint 2 (East-West Visibility), Sprint 3 (Production Hardening), and Sprint 4 (Assessment Completeness) are now closed.
> **18 of 18 Azure rules are active.** Beta deployment sequence is ready to run.

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

## Post-Beta Roadmap

| Item | Priority | Notes |
| --- | --- | --- |
| Production deployment | **High** | Run `031` targeting `prod` after dev Beta validation. Document prod env var gap first (`AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_CONTAINER_ENGAGEMENTS`). |
| AWS Provider Expansion (Phase G) | High | Azure parity; needs Phase C discovery stubs for AWS |
| Phase C: Azure network/security discovery stubs | Medium | `azure_network/security` Phase C — currently raise NotImplementedError |
| Client portal hardening | Medium | Retention engine (90 days), SAS token TTL enforcement |
| App Gateway capacity metrics | Low | `CapacityUnits`, `BackendLastByteResponseTime` — WAF efficacy enrichment |
| Defender for Cloud network recommendations | Low | `Microsoft.Security/assessments/read` — enrichment for Page 7 |
| CISA ZTMM v2 framework mappings | Low | Zero Trust maturity model — per-finding mapping |
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

**18 of 18 rules active.**

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
