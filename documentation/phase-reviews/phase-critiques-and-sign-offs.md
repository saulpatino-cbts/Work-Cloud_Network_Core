# CNA Platform — Phase Critiques & Architect Sign-Offs

All six delivery phases have been reviewed, gap-closed, and signed off.
This document is the permanent record of those reviews.

> **Signed off by:** Saul Patino Jr. — AWS Certified Solutions Architect Professional | Microsoft Certified Azure Solutions Architect Expert
> **All phases closed:** 2026-03-05

---

## Summary

| Phase | Gaps Found | Gaps Closed | Status |
|---|---|---|---|
| A — Architecture & Infrastructure | 16 | 16 | ✅ CLOSED |
| B — Diagram Engine | 14 | 14 | ✅ CLOSED |
| C — Discovery Engine | _(reviewed inline with A/B)_ | — | ✅ CLOSED |
| D — AI Analysis Engine | 16 | 16 | ✅ CLOSED |
| E — Report Generation Engine | 18 | 18 | ✅ CLOSED |
| F — Delivery Portal | 17 | 17 | ✅ CLOSED |

---

## Phase A — Architecture & Infrastructure

**STATUS: ✅ CLOSED — All 16 gaps resolved.**
**Signed:** 2026-03-05 | **Commit:** `60709572476f1e2fcd7f56356c55f3d7b768471c`

### Architecture Decisions — CLOSED

**~~DD-001: Delivery-only (no pre-sales)~~**
`documentation/client-packet/engagement-entry-model.md` — full pre-sales-to-delivery flow, pricing tier model, and four required gate documents. Platform is delivery-only by design.

**~~DD-002: Observed state only, no assumptions~~**
`cna/core/observed_state_validator.py` — two-layer enforcement: (1) 16 linguistic hedge patterns blocked via regex, (2) every finding must reference at least one `evidence_id`. `ObservedStateViolation` raised on violation.

**~~DD-003: Recommendations via MCP servers only~~**
MCP server selection specified in `cna/modules/*/module.yaml`. Router deferred to Phase D by design — cannot route until Phase C discovery output exists.

**~~DD-006: All regions enumerated dynamically~~**
`cna/core/throttle.py` — `PaginationCursor` (AWS NextToken / Azure skipToken), `ConcurrencyLimiter` (async semaphore, 10 AWS / 5 Azure), `with_retry()` (exponential backoff, 5 retries).

**~~DD-008: AI analyzes only our collected data~~**
`cna/core/observed_state_validator.py` + `topology_schema.py` (versioned Pydantic contract). AI pipeline calls `validate_observed_state()` before persisting any finding.

**~~DD-009: Human review gate blocks report generation~~**
`cna/core/persistence.py` — `write_audit_event()` logs every review action. `cna/core/exceptions.py` — `ReviewGateError` raised by report engine when `review_complete=False`.

**~~DD-011: Landing zone = Mermaid docs, not IaC~~**
`documentation/policies/lz-scope-boundary.md` — client-facing doc explaining Mermaid choice and explicit IaC exclusion.

**~~DD-014: Executive PPTX auto-generated~~**
`cna/report_engine/templates/executive_summary.j2` — 10-section reviewed structure. `finding_detail.j2` — per-finding detail. Structure is human-reviewed; AI does not improvise slide count.

**~~DD-015: EN/JA language toggle~~**
`documentation/policies/ja-translation-protocol.md` — 4-step protocol, 10-term approved glossary, `ja_review_complete` flag blocks JA publication.

### Structural Gaps — CLOSED

| Gap | Resolution |
|---|---|
| No persistence layer | `cna/core/persistence.py` — atomic writes, checkpoints, file locking, audit trail |
| No auth / credential model | `cna/core/auth.py` — STS AssumeRole, DefaultAzureCredential, KeyVault provider |
| No engagement ID strategy | `generate_engagement_id()` — `{client_slug}-{YYYYMMDD}-{4-hex}` |
| No concurrency / locking | `acquire_lock()` / `release_lock()` — advisory `.lock` file |
| No error taxonomy | `cna/core/exceptions.py` — 12-exception hierarchy with documented handling |
| No logging infrastructure | `cna/core/logging_config.py` — JSON structured log + Rich console + audit trail |
| No secret scanning in CI | `.pre-commit-config.yaml` — `detect-secrets` + `gitleaks`; CI `gitleaks-action@v2` |
| No pre-commit hooks | ruff, trailing-whitespace, YAML/JSON/TOML, private key detection, no-commit-to-main |
| No branching strategy | `develop` branch, CI on both main/develop, branch protection documented |
| Module `depends_on` not enforced | `cna/core/module_runner.py` + `scripts/validate_module_deps.py` (CI) |
| No data schema for discovery | `cna/core/topology_schema.py` — 16 AWS + 12 Azure models, schema v1.0.0 |
| No diagram input validation | `drawio_generator.py` — `ValueError` on blocked input, `_safe()` HTML escaping |
| No output directory structure | `EngagementStore.output_paths` — 5-path structure, created on `cna init` |
| No rollback / idempotency | `write_discovery_checkpoint()` + `list_completed_checkpoints()` — resume support |
| Superficial test coverage | 28 unit tests for diagram engine; CLI/MCP tests deferred to Phase C |
| No engagement templates | `executive_summary.j2`, `finding_detail.j2` — reviewed 10-section structure |
| No client data handling policy | `documentation/policies/data-handling-policy.md` — GDPR/SOC2/HIPAA positions |

---

## Phase B — Diagram Engine

**STATUS: ✅ CLOSED — All 14 gaps resolved.**
**Signed:** 2026-03-05

### Gaps & Resolutions

| # | Gap | Resolution |
|---|---|---|
| 1 | `diagrams_generator.py` was empty stub | Full Mingrammer implementation — `generate_aws_vpc_diagram()`, `generate_azure_vnet_diagram()`, graceful fallback |
| 2 | Export pipeline — no `drawio` CLI in container | `Dockerfile` updated with headless draw.io install via `xvfb-run`; `CNA_SKIP_RASTER=true` for local dev |
| 3 | No Mermaid CLI (`mmdc`) integration | `Dockerfile` installs `@mermaid-js/mermaid-cli`; `mmdc_to_svg()` implemented in export pipeline |
| 4 | TGW cell ID lookup broken — no VPC edges | `vpc_cell_map: dict[str, str]` maintained during VPC render; TGW-to-VPC edges now rendered |
| 5 | VPC peering not rendered | Peering edges rendered with accepter account/region label; cross-account stub node added |
| 6 | Route tables not rendered | Route entries in draw.io tooltip; `generate_route_table_detail()` for technical appendix |
| 7 | Direct Connect absent from diagrams | `STYLE_DX` node above VPC row, connected to TGW via VGW attachment |
| 8 | Missing schema resources (SGs, NACLs, Firewall, etc.) | `topology_schema.py` v1.1.0 — added `SecurityGroup`, `NACL`, `VpnGateway`, `NetworkFirewallPolicy`, `AzureFirewall`, `ApplicationGateway`, `PrivateDnsZone`, `ExpressRouteCircuit` |
| 9 | No diagram naming convention | `cna/diagram_engine/naming.py` — `{engagement_id}-{platform}-{type}-{account}-{region}.{ext}` |
| 10 | No retry/timeout for draw.io subprocess | 3 retries with 5s delay; SVG corruption detection via `xml.etree.ElementTree` |
| 11 | Hardcoded cairosvg scale | `dpi` + `max_dimension_px` configurable; scale computed dynamically; `CNA_DIAGRAM_DPI` env var |
| 12 | No XML validation before write | `_validate_xml()` — `ElementTree.fromstring()` check before every `.drawio` write |
| 13 | Zero export pipeline tests | `tests/unit/test_export_pipeline.py` — 12 tests covering all fallback/error paths |
| 14 | README not updated | README fully rewritten to reflect Phase B and Phase C status |

---

## Phase D — AI Analysis Engine

**STATUS: ✅ CLOSED — All 16 gaps resolved.**
**Signed:** 2026-03-05

### Gaps & Resolutions

| Gap(s) | File | Resolution |
|---|---|---|
| Empty engine stubs | `cna/ai_engine/analysis_engine.py` | Full analysis engine with AWS + Azure finding rules, deduplication, severity model, framework mapping enforcement |
| Empty recommendation stub | `cna/ai_engine/recommendation_engine.py` | Recommendation engine strictly separated from finding generation (DD-003) |
| Empty MCP router | `cna/ai_engine/mcp_client/mcp_router.py` | MCP routing logic — routes by platform per module.yaml |
| Empty MCP clients | `aws_mcp_client.py`, `azure_mcp_client.py` | Full client implementations |
| No `observed_state` enforcement | `cna/ai_engine/observed_state_enforcer.py` | Validator called before every finding write |
| No severity model | `cna/core/findings_schema.py` | `Severity` enum (CRITICAL/HIGH/MEDIUM/LOW) + escalation threshold |
| No `cna analyze` CLI | `cna/cli/analyze.py` | CLI entry point with Rich progress output |
| Zero tests | `tests/unit/test_analysis_engine.py` | Full test suite |
| `FindingsReport` not written | `EngagementStore.write_findings_report()` | Atomic write to engagement store for Phase E consumption |

**Architect confirmation:**
- Every finding has `observed_state` (fact, not assumption)
- Every finding has `severity` (CRITICAL/HIGH/MEDIUM/LOW)
- Every finding has at least one `framework_mapping`
- Findings and recommendations written by strictly separate code paths (DD-003)
- Deduplication key `{finding_id}:{resource_id}` prevents duplicates
- CRITICAL findings trigger `EscalationEngine` before analysis completes (DD-016)

---

## Phase E — Report Generation Engine

**STATUS: ✅ CLOSED — All 18 gaps resolved.**
**Signed:** 2026-03-05

### Gaps & Resolutions

| Gap(s) | File | Resolution |
|---|---|---|
| All report_engine files were stubs | `executive_report.py`, `technical_report.py`, `presentation_deck.py`, `regional_report.py`, `deliverable_manifest.py`, `knowledge_transfer.py` | Full implementations |
| DD-009 review gate not enforced | `cna/report_engine/render_pipeline.py` | `ReviewGateError` raised structurally if `review_complete=False` |
| No `cna report` CLI | `cna/cli/report.py` | `cna report` + `cna report preview` |
| Incomplete template set | `cna/report_engine/templates/` | Full template set with severity colors, framework table, recommendations |
| No render pipeline | `render_pipeline.py` | Jinja2 → HTML → PDF chain implemented |
| No PPTX builder | `presentation_deck.py` | `python-pptx` builder covering all 10 required sections |
| No JA gate | `regional_report.py` | `JaReviewGateError` raised if `ja_review_complete=False` (DD-015) |
| No HTML preview | `html_preview.py` | Preview path requiring no PDF toolchain |
| No deliverable manifest | `deliverable_manifest.py` | `DeliverableManifest` written to `EngagementStore` for Phase F |
| No version stamping | `deliverable_manifest.py` | Files stamped with `engagement_id`, `schema_version`, ISO 8601 timestamp |
| Zero tests | `tests/unit/test_report_engine.py` | Full test suite |

---

## Phase F — Delivery Portal

**STATUS: ✅ CLOSED — All 17 gaps resolved.**
**Signed:** 2026-03-05

### Gaps & Resolutions

| Gap(s) | File | Resolution |
|---|---|---|
| All portal files were stubs | `portal_generator.py`, `s3_deployer.py`, `access_manager.py` | Full implementations |
| No Azure Blob deployer | `cna/delivery_portal/azure_blob_deployer.py` | New file — SAS tokens, content-type headers, upload progress |
| No `cna publish` CLI | `cna/cli/publish.py` | `cna publish` + `cna publish status` |
| No retention enforcement | `cna/delivery_portal/retention_engine.py` | `RetentionExpiredError` if past 90-day window (DD-019) |
| No staleness detection | `portal_generator.py` | Reads `DeliverableManifest.findings_checksum` vs current checksum (DD-013) |
| No pre-signed URLs / SAS tokens | `access_manager.py` | S3 pre-signed URLs + Azure SAS tokens, configurable TTL, 7-day hard cap |
| No CORS on S3 | `s3_deployer.py` | CORS applied on every publish run |
| No content-type headers | Both deployers | `application/pdf`, PPTX MIME type, `text/html` per extension |
| Zero tests | `tests/unit/test_delivery_portal.py` | Full test suite |

**Architect confirmation:**
- `RetentionEngine.check()` raises `RetentionExpiredError` past 90 days — DD-019 enforced structurally
- Staleness detection wired end-to-end — DD-013 closed
- Pre-signed URLs and SAS tokens: configurable TTL, hard cap 7 days
- CORS applied to S3 bucket on every publish
- Azure Blob deployer uses `DefaultAzureCredential` — consistent with Phase C auth pattern

---

_Consolidated from: `TODO_PhaseA.md`, `TODO_PhaseB.md`, `TODO_PhaseD.md`, `TODO_PhaseE.md`, `TODO_PhaseF.md`_
_Original files removed 2026-03-08._
