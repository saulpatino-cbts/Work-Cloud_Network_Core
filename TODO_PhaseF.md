# TODO_PhaseF.md — Phase F: Delivery Portal
## Critique, Gap Closure & Architect Sign-Off

> Authored: 2026-03-05 | Closed: 2026-03-05 | Signed off: Saul Patino Jr.

---

## The Critique (No Fluff)

### P0 — Every delivery_portal file is a stub

| # | Gap | File | Verdict |
|---|---|---|---|
| 1 | `portal_generator.py` = `# TODO: Phase F` | `cna/delivery_portal/portal_generator.py` | **Dead file.** |
| 2 | `s3_deployer.py` = `# TODO: Phase F` | `cna/delivery_portal/s3_deployer.py` | **Dead file.** |
| 3 | `access_manager.py` = `# TODO: Phase F` | `cna/delivery_portal/access_manager.py` | **Dead file.** |

### P0 — Critical design contract violations

| # | Gap | Impact |
|---|---|---|
| 4 | No `cna publish` CLI command — Phase F has no entry point whatsoever | Platform cannot deliver anything to a client |
| 5 | No retention enforcement — DD-019 requires engagement data deleted 90 days post-delivery; nothing in code tracks or enforces this | Legal/contractual liability |
| 6 | No staleness badge rendering — DD-013 stored a checksum per deliverable in Phase E; Phase F never reads it | Clients could download stale reports after re-analysis without warning |
| 7 | No Azure Blob Storage deployer — `s3_deployer.py` is a stub and Azure support is completely absent | Platform is AWS-only at delivery despite being a dual-cloud product |

### P1 — Missing coverage that makes portal unusable

| # | Gap |
|---|---|
| 8 | No portal HTML template — nothing to generate a client-facing download page |
| 9 | No pre-signed URL generation (S3) — `access_manager.py` is empty |
| 10 | No SAS token generation (Azure Blob) — Azure equivalent of pre-signed URLs not implemented |
| 11 | No expiry enforcement on pre-signed URLs — default TTL not defined, no max cap |
| 12 | No `cna publish status` command — no way to check if a portal is live or expired |
| 13 | No CORS configuration on S3 bucket — browser downloads will fail without it |
| 14 | No content-type headers on uploaded files — PDFs served as `application/octet-stream`, PPTX files corrupt in browser |
| 15 | No upload progress reporting — large PDF/PPTX uploads are silent |
| 16 | Zero unit tests for any delivery portal logic |
| 17 | No `documentation/architecture/phase-f-portal.md` |

---

## Gap Closures

All 17 gaps closed in this commit.

| Gap(s) | File |
|---|---|
| 1, 6, 8, 13, 14, 15 | `cna/delivery_portal/portal_generator.py` |
| 2, 13, 14, 15 | `cna/delivery_portal/s3_deployer.py` |
| 7, 10, 11, 14, 15 | `cna/delivery_portal/azure_blob_deployer.py` |
| 3, 9, 10, 11 | `cna/delivery_portal/access_manager.py` |
| 5, 12 | `cna/delivery_portal/retention_engine.py` |
| 4, 12 | `cna/cli/publish.py` |
| 16 | `tests/unit/test_delivery_portal.py` |
| 17 | `documentation/architecture/phase-f-portal.md` |

---

## Sign-Off

**All 17 gaps closed. Retention enforced in code. Staleness detection wired. Dual-cloud delivery (S3 + Azure Blob) implemented. Full test suite passing.**

As a distinguished cloud architect with active AWS Solutions Architect Professional
and Azure Solutions Architect Expert certifications, I confirm:

- `RetentionEngine.check()` raises `RetentionExpiredError` if engagement is past 90-day window — DD-019 enforced structurally
- Staleness detection reads `DeliverableManifest.findings_checksum` and compares to current `FindingsReport` checksum — DD-013 wired end-to-end
- Pre-signed URLs (S3) and SAS tokens (Azure Blob) have configurable TTL with a hard cap of 7 days — no indefinite access links
- CORS configuration applied to S3 bucket on every publish run
- Content-type headers set per file extension: `application/pdf`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `text/html`
- `cna publish status` checks live URL reachability and expiry
- Azure Blob deployer uses `DefaultAzureCredential` — consistent with Phase C auth pattern

**Phase F: CLOSED.**
**Platform complete through Phase F. All six phases shipped.**

— Saul Patino Jr., AWS SAP | Azure SAE | 2026-03-05
