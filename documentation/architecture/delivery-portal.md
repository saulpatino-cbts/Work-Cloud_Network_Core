# Delivery Portal Architecture

> Version: 1.0.0 | Status: ACTIVE | Date: 2026-03-05

The Delivery Portal publishes completed engagement reports to a time-limited, access-controlled cloud storage location and generates a client-facing portal page. The client receives a single URL with no login required — the pre-signed URL or SAS token is the credential.

---

## Publish Flow

```
cna publish run --engagement-id <id> --cloud [aws|azure] --ttl-days 7
        │
        ├─ 1. Verify review_complete=True (ReviewGateError if not)
        ├─ 2. Collect report files from EngagementStore
        ├─ 3. Upload to cloud storage (S3 or Azure Blob)
        ├─ 4. Generate pre-signed URL (AWS) or SAS token (Azure)
        │     └─ TTL cap: 7 days maximum (DD-019)
        ├─ 5. Generate portal HTML page (engagement summary + download links)
        ├─ 6. Write portal URL to engagement.json
        └─ 7. Audit log entry: published_by, timestamp, url, ttl_expires

cna publish status --engagement-id <id>
        └─ Returns: portal URL, TTL expiry, files published, upload timestamp
```

---

## Storage Targets

| Platform | Resource | Object Path | Access Control |
|---|---|---|---|
| AWS | S3 Bucket: `cna-deliverables-prod` | `{engagement_id}/` prefix | Pre-signed URL (7-day max) + bucket policy blocks public access |
| Azure | Blob Container: `cna-deliveries` | `{engagement_id}/` prefix | SAS token (7-day max) + container access = Private |

**No object in either storage target is ever publicly accessible without a valid time-limited credential.**

---

## Retention (DD-019)

- Reports retained for **90 days** after delivery date
- Retention engine runs as a scheduled job (`cna publish cleanup`)
- Deletion is logged to audit trail with engagement ID and file list
- Client may request early deletion — completed within 5 business days
- See `documentation/policies/data-handling-policy.md` for full retention policy

---

## CD Pipeline Integration

The `cd-publish.yml` GitHub Actions workflow automates the publish step for production releases:

```
trigger: workflow_dispatch (manual) or tag vX.Y.Z-release
jobs:
  publish-aws:  OIDC → sts:AssumeRoleWithWebIdentity → CNA-Publish role → S3
  publish-azure: OIDC → Federated Identity → Azure Blob Storage
```

See `documentation/workflows-guide.md` for full workflow documentation.
