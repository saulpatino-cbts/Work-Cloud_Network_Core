# MVP-Cloud Network Assessment (CNA)

> **Cloud Network & Security Assessment Platform**
> Vendor-side toolchain for multi-cloud network architecture discovery,
> AI-assisted analysis, diagram generation, and stakeholder delivery.

## Quick Start

```bash
docker pull ghcr.io/saulpatinojr/cna:latest
cna init --client <client-name> --regions us,emea,japan
cna discover aws --role <role-arn> --external-id <id>
cna discover azure --sp-id <id> --tenant <id>
cna analyze
cna diagram generate --all
cna review
cna report --type all
cna publish
```

## Platform Phases

| Phase | Component | Priority |
|---|---|---|
| A | Repo skeleton + infrastructure | ✅ Complete |
| B | Diagram generation pipeline | 🔴 TOP PRIORITY |
| C | Discovery engine (AWS + Azure) | Next |
| D | AI analysis engine + MCP integration | Following |
| E | Report generation engine | Following |
| F | Delivery portal (S3 static site) | Following |

## Documentation Index

| Document | Location |
|---|---|
| Architecture Overview | [documentation/architecture/overview.md](documentation/architecture/overview.md) |
| Design Decisions Log | [documentation/design/design-decisions.md](documentation/design/design-decisions.md) |
| Client Welcome Packet | [documentation/client-packet/welcome-packet.md](documentation/client-packet/welcome-packet.md) |
| Environment Info Form | [documentation/client-packet/environment-info-form.md](documentation/client-packet/environment-info-form.md) |
| Permission Grant Guide | [documentation/client-packet/permission-grant-guide.md](documentation/client-packet/permission-grant-guide.md) |
| Module Guide | [documentation/development/module-guide.md](documentation/development/module-guide.md) |
| Diagram Generation Guide | [documentation/development/diagram-generation.md](documentation/development/diagram-generation.md) |
| Repo Structure | [documentation/architecture/repo-structure.md](documentation/architecture/repo-structure.md) |

## Three Critical Platform Guarantees

1. **Diagram generation** — Phase B, first code deliverable, non-negotiable
2. **Silent failure detection** — every blocked resource logged and surfaced in reports
3. **Human review gate** — `cna report` is CLI-blocked without architect sign-off

## License

Internal use only — © 2026 Your Organization
