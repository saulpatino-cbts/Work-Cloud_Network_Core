# Report Generation Architecture

> Version: 1.0.0 | Status: ACTIVE | Date: 2026-03-05

The Report Generation engine transforms a `FindingsReport` from the EngagementStore into client-ready deliverables: a PDF report, an executive PPTX deck, and optionally a Japanese-language regional version. The human review gate (DD-009) is enforced here — no report is generated unless `review_complete=True` in the engagement state.

---

## Review Gate (DD-009)

```
cna report generate --engagement-id <id>
        │
        ├─ 1. Load engagement.json
        ├─ 2. Check review_complete flag
        │     ├─ False → raise ReviewGateError (report aborted)
        │     └─ True → continue
        ├─ 3. Load findings_report.json from EngagementStore
        ├─ 4. Render templates (Jinja2)
        ├─ 5. Generate PDF + PPTX
        └─ 6. Write to engagements/{id}/reports/

cna review complete --engagement-id <id> --operator <name>
        └─ Sets review_complete=True + writes audit.jsonl entry
```

---

## Output Deliverables

| Deliverable | Template | Format | Audience |
|---|---|---|---|
| Executive Summary Report | `executive_summary.j2` | PDF | Client CxO |
| Executive PPTX Deck | Rendered from `executive_summary.j2` sections | PPTX | Client CxO presentation |
| Finding Detail Pages | `finding_detail.j2` | PDF (appendix) | Client technical team |
| Japanese Regional Report | EN report + DeepL + glossary + JA review gate | PDF | Japan-based clients |

---

## Template Structure

### `executive_summary.j2` — 10 sections

1. Cover (engagement ID, client name, date, CNA logo)
2. Executive Summary (3-sentence plain-language summary)
3. Findings by Severity (CRITICAL / HIGH / MEDIUM / LOW counts)
4. Top 5 Findings (hard-capped — never more than 5 on executive page)
5. Diagram Gallery (generated diagrams embedded)
6. Framework Alignment (WAF pillars covered)
7. Scope Notice (what was and was not in scope)
8. Methodology (observed state only, evidence-linked)
9. Engagement Metadata
10. Signature block (review operator + timestamp)

### `finding_detail.j2` — per finding

- Finding ID, title, severity badge
- Affected resource(s) with ARN/resource ID
- Observed state (verbatim, evidence-linked)
- Framework mappings (WAF pillar + control)
- Recommendation (sourced from MCP — labeled as vendor guidance)
- Evidence reference(s)

---

## Japanese Translation Protocol (DD-015)

See `documentation/policies/ja-translation-protocol.md` for the full 4-step protocol.

The `ja_review_complete` flag in engagement state must be `True` before the JA report is published. This flag is set separately from `review_complete` and requires a native speaker review attestation in the audit log.

---

## Output File Naming

```
engagements/{engagement_id}/reports/
  executive/
    {engagement_id}_executive_summary_{ISO_TIMESTAMP}.pdf
    {engagement_id}_executive_deck_{ISO_TIMESTAMP}.pptx
  findings/
    {engagement_id}_findings_detail_{ISO_TIMESTAMP}.pdf
    findings_report.json
  regional/
    {engagement_id}_ja_executive_summary_{ISO_TIMESTAMP}.pdf
```
