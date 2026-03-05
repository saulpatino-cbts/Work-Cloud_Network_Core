# Client Data Handling Policy

> Closes TODO_PhaseA: No Client Data Handling Policy.
> Version: 1.0.0 | Status: ACTIVE | Effective: 2026-03-05

---

## Scope

This policy applies to all cloud configuration data collected by the CNA platform
during delivery engagements. It covers collection, storage, access, retention,
and deletion of client cloud topology data (API responses, resource configurations,
IP ranges, security group rules, route tables, and derived findings).

---

## What We Collect

- Cloud resource configurations (VPCs, VNets, subnets, route tables, TGW attachments,
  security groups, NSGs, IAM policies)
- API responses from AWS and Azure discovery calls
- Derived topology models (Pydantic models serialized to JSON)
- Findings and recommendations generated from collected data

We do **not** collect:
- Customer application data, database contents, or business records
- Secrets, credentials, or encryption keys
- Network traffic or packet-level data
- Personal data (PII) of client employees

---

## Storage

| Environment | Storage Location | Encryption |
|---|---|---|
| Local (default) | Operator workstation `./engagements/` | OS disk encryption required (BitLocker / FileVault) |
| Azure Blob (optional) | Azure Blob Storage, engagement-specific container | Azure Storage Service Encryption (SSE) with customer-managed keys |

All engagement directories are created with `700` permissions (owner-only).
Azure Blob containers are private with no public access.

---

## Access Control

- Only the delivery lead and named engagement team members may access engagement data.
- Access to Azure Blob Storage is controlled via Azure RBAC (Storage Blob Data Contributor).
- No data is shared with third parties, subcontractors, or model training pipelines.
- Client data is never used for AI model training, fine-tuning, or evaluation.

---

## Retention and Deletion

| Phase | Retention |
|---|---|  
| Active engagement | Duration of engagement + 90 days |
| Post-delivery | 90 days after final deliverable delivery |
| On client request | Deleted within 5 business days |
| Default expiry | Permanent deletion at 90-day mark |

Deletion is:
- Local: `rm -rf ./engagements/<engagement_id>/`
- Azure Blob: container deletion + soft-delete expiry confirmation

Deletion confirmation is logged in the engagement audit log.

---

## Regulatory Considerations

| Regulation | Position |
|---|---|
| GDPR | Client cloud configuration data is not personal data under GDPR Art. 4. If any PII is incidentally discovered (e.g., resource names containing employee names), it is redacted before storage. |
| SOC 2 Type II | This platform is not currently SOC 2 certified. Enterprise clients requiring SOC 2 evidence should request the data handling addendum. |
| HIPAA | CNA does not collect, store, or process PHI. Engagements involving healthcare clients must confirm no PHI exists in resource tag values before discovery runs. |

---

## Client Agreement

Every engagement requires a signed **Data Handling Agreement** (DHA) before
discovery begins. The DHA template is in `documentation/client-packet/data-handling-agreement-template.md`.

The signed DHA is stored outside the engagement directory (not in the repo).

---

## Incident Response

If client data is accidentally exposed (e.g., committed to a public repo,
shared with wrong party):

1. Immediately notify the delivery lead and client contact.
2. Revoke access and rotate any affected credentials within 1 hour.
3. Document the incident in the engagement audit log.
4. Follow the client's incident response procedure if one exists.
5. Engage legal counsel if the exposure involves regulated data.
