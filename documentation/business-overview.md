# CNA Platform — Business Overview

## What the Platform Does

The Cloud Network Assessment (CNA) platform is an automated toolchain that lets CBTS analysts
run a full security and architecture review of a client's Azure or AWS cloud network — in hours
instead of weeks — and deliver polished, professional reports directly to the client.

Today, a network assessment is largely manual: an analyst logs into a client's cloud console,
clicks through dozens of screens, documents findings in spreadsheets, writes recommendations
by hand, builds PowerPoint decks, and emails PDFs. That process takes days of billable labor
per engagement.

CNA replaces that entire workflow with a single platform:

1. **Discovery** — Connects to a client's Azure subscription or AWS account using read-only
   credentials and automatically inventories everything: VNets, subnets, NSGs, firewalls, NVAs,
   load balancers, private endpoints, route tables, App Gateways, NAT gateways, ExpressRoute
   circuits, public IPs. What used to take half a day of clicking takes minutes.

2. **AI-Powered Analysis** — The discovered topology is fed to Azure OpenAI, which generates
   security findings categorized by severity (Critical / High / Medium / Low) and mapped to
   compliance frameworks (NIST CSF, CIS Controls v8, Azure CAF). The AI identifies gaps a
   human might miss — unprotected subnets, missing flow logs, open NSG rules, absent firewalls.

3. **Assessment Presentation** — Produces a multi-page interactive report: an executive overview
   with risk score and maturity radar, a technical deep-dive with every finding, a phased
   remediation roadmap, and a compliance posture view. No PowerPoint required.

4. **Client Delivery** — Clients receive a time-limited, authenticated delivery portal to view
   their deliverables — no emailing PDFs, no shared drives, no sensitive findings in inboxes.

---

## How It Saves CBTS Money

| What changes | Impact |
|---|---|
| Discovery is automated | An engagement that took 2–3 analyst days of manual inventory now takes ~30 minutes of machine time |
| Findings are AI-generated | First-pass analysis and recommendations are drafted automatically — analyst reviews and adjusts instead of writing from scratch |
| Reports are generated, not built | No more building PowerPoint decks and Word reports by hand per engagement |
| The platform is reusable | Every new client engagement runs through the same workflow — no reinventing the wheel |
| Multi-analyst, multi-engagement | Multiple analysts can run concurrent engagements from one shared platform; nothing lives on a personal laptop |

Rough math: if a manual assessment costs 3 analyst days and CNA reduces that to half a day of
review and delivery, that is roughly 80% labor reduction per engagement. At scale across many
engagements per year that is significant recovered margin — or the capacity to take on more
engagements without adding headcount.

---

## How It's Better for Clients

- **Faster turnaround** — Clients receive findings in days, not weeks
- **More thorough** — Automated discovery does not miss resources a human skimming the portal might overlook
- **Consistent quality** — Every client gets the same rigorous analysis framework regardless of which analyst runs it
- **Professional deliverables** — Interactive presentation-quality reports, not a spreadsheet export
- **Clear action plan** — The remediation roadmap specifies what to fix, in what order, and by when — not just a list of problems
- **Secure delivery** — Time-limited authenticated portal instead of emailing sensitive security findings as PDF attachments

---

## Target Users

| Role | Who they are | What they do in the platform |
|---|---|---|
| **Analyst** | CBTS engineer running the engagement | Triggers discovery, reviews AI findings, edits/adds findings, generates reports |
| **Reviewer** | Senior CBTS engineer or manager | Reviews and approves findings before delivery |
| **Client** | Client stakeholder | Views their deliverables through the authenticated portal |
| **Admin** | CBTS platform administrator | Manages users, engagements, and platform settings |

---

## Supported Cloud Platforms

| Platform | Discovery | Analysis | Status |
|---|---|---|---|
| Microsoft Azure | VNets, NSGs, Firewalls, NVAs, LBs, Gateways, Private Endpoints, ExpressRoute | Azure OpenAI (GPT-4o) | ✅ Complete |
| Amazon Web Services | VPCs, Security Groups, Route Tables, NAT, IGW, TGW, NACLs | Azure OpenAI (GPT-4o) | ⏳ In progress |
