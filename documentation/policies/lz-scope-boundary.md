# Landing Zone Scope Boundary

> Closes TODO_PhaseA: DD-011 not explained to client.
> This document is included in the client welcome packet by reference.
> Version: 1.0.0

---

## What This Engagement Delivers

The Cloud Network Assessment includes **landing zone architecture documentation**.
This means:

- Architecture diagrams of your existing or recommended landing zone design
- Mermaid-based flowcharts showing management layer, connectivity hub,
  workload placement, and security control positioning
- Written design rationale aligned to AWS Landing Zone Accelerator and
  Azure Landing Zone (Enterprise-Scale) reference architectures
- Findings where your current environment deviates from landing zone best practices

---

## What This Engagement Does NOT Deliver

This engagement **does not deploy, configure, or modify any infrastructure**.

Specifically, we do not produce:
- Terraform, Bicep, ARM templates, or CloudFormation
- AWS Control Tower or Azure Landing Zone Accelerator configurations
- Any IaC that could be applied to your environment

---

## Why Mermaid Diagrams?

Mermaid diagrams are:
- **Text-based** — version-controlled in your repo, diff-able, auditable
- **Rendered as SVG/PNG** — embedded in your report and portal
- **Portable** — render in GitHub, GitLab, Confluence, Notion, and VS Code
- **Not proprietary** — no Visio or Lucidchart license required

Every Mermaid diagram is also exported as a `.drawio` file so your team can
edit it in draw.io / diagrams.net without any additional tooling.

---

## If You Need IaC

If your engagement scope requires IaC output, this should be defined in
your Statement of Work before discovery begins. IaC delivery is a separate
engagement phase with separate pricing and timeline.
