# CNA Platform Architecture Overview

## Three-Tier Model

| Tier | Location | Purpose |
|---|---|---|
| Assessor Workstation | Docker, any OS | CLI — `cna` commands |
| Vendor Cloud Backend | Your Azure subscription | AI analysis, engagement storage, Azure OpenAI, Key Vault |
| Client-Facing Portal | Your AWS account | S3 + CloudFront static delivery to stakeholders |

## Platform Phases

| Phase | Component | Status |
|---|---|---|
| A | Repo skeleton + core models + module registry | ✅ Complete |
| B | Diagram generation pipeline | 🔴 TOP PRIORITY — Next |
| C | Discovery engine (AWS + Azure) | Planned |
| D | AI analysis engine + MCP integration | Planned |
| E | Report generation engine | Planned |
| F | Delivery portal (S3 static site) | Planned |

## Three Critical Platform Guarantees

These are enforced in code, not just policy:

1. **Diagram generation** — Phase B, first code deliverable, non-negotiable for every engagement
2. **Silent failure detection** — every blocked account/region/service is logged and surfaced in all reports
3. **Human review gate** — `cna report` CLI-blocked (`review_complete=False`) until architect sign-off

## Data Flow

```
Client Cloud Environment
        |
        v  (read-only, least-privilege)
  Discovery Engine (Phase C)
        |
        v
  Engagement Data Store (Azure Storage)
        |
        v
  AI Analysis Engine (Phase D)
  [AWS MCP + Azure MCP — our data only]
        |
        v
  Human Review Gate (Phase D)
        |
        v
  Report Engine (Phase E)
        |
        v
  Delivery Portal (Phase F)
  [S3 + CloudFront — client stakeholders]
```
