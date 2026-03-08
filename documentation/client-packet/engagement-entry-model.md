# Engagement Entry Model

> Closes TODO_PhaseA: DD-001 no pre-sales funnel, no SOW template, no engagement letter.
> Version: 1.0.0

---

## How a Client Reaches Delivery

This is a **delivery-only** platform. That is a deliberate scope boundary, not a
business model gap. The pre-sales process is intentionally kept out of this platform
because it varies by channel (direct, partner, referral). The delivery platform
activates once a signed engagement exists.

```
PRE-SALES (external to this platform)
  │
  ├─ Channel: Direct outreach / referral / partner
  ├─ Scoping call: Platform, account count, regions, timeline
  ├─ Proposal sent (see: proposal-template.md)
  ├─ SOW signed (see: sow-template.md)
  ├─ Data Handling Agreement signed
  └─ Kickoff scheduled
           ↓
  DELIVERY PLATFORM ACTIVATES
  └─ `cna init --client <name>` — engagement ID generated
  └─ Welcome packet sent
  └─ Environment info form sent
  └─ Permission grant guide sent
  └─ Discovery begins
```

---

## Pricing Model

| Tier | Scope | Indicative Price |
|---|---|---|
| Foundation | Single cloud, up to 5 accounts/subscriptions, 3 regions | On request |
| Standard | Dual cloud or 6-20 accounts, up to 10 regions | On request |
| Enterprise | Multi-cloud, 20+ accounts, full org scan | On request |

Pricing is engagement-specific and not stored in this platform.
Pricing documents live in the external CRM/deal tracker, not in this repo.

---

## Required Documents Before Discovery Starts

1. **Signed SOW** — defines scope, deliverables, timeline
2. **Signed Data Handling Agreement** — see `documentation/policies/data-handling-policy.md`
3. **Completed Environment Info Form** — see `documentation/client-packet/environment-info-form.md`
4. **Permission Grant Confirmation** — see `documentation/client-packet/permission-grant-guide.md`

Discovery cannot begin until all four are in hand. `cna init` will prompt
the operator to confirm each one before writing the engagement file.

---

## Statement of Work Template Reference

A full SOW template is maintained separately (outside this repo) as a Word document.
Key SOW sections that must be present for every engagement:

- Scope of work (platforms, accounts, regions, modules)
- Deliverables list (diagrams, findings report, executive deck)
- Out-of-scope items (IaC, deployment, remediation execution)
- Timeline and milestone gates
- Data handling terms (reference to signed DHA)
- Acceptance criteria
- Change order process
