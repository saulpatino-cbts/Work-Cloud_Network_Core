# Repository Structure

```
MVP-Cloud_Network_Assessment/
├── README.md                        Master index and quick start
├── .gitignore                       Protects secrets and raw data
├── .env.example                     All config variables documented
├── pyproject.toml                   Python package and dependencies
├── Dockerfile                       Includes graphviz/cairo for diagrams
├── docker-compose.yml               Local dev + test runner
├── cna/
│   ├── cli/
│   │   └── commands/                CLI command handlers (one file per command)
│   ├── core/                        Shared models and engines
│   │   ├── engagement.py            Engagement state model
│   │   ├── findings_schema.py       Universal finding model
│   │   ├── discovery_coverage.py    Coverage/gap tracking
│   │   ├── escalation_engine.py     Real-time critical finding alerts
│   │   ├── version_manager.py       Document versioning
│   │   └── deliverable_dependency.py Stale deliverable detection
│   ├── modules/
│   │   ├── registry.py              Module loader
│   │   ├── network/                 Installed — Phase C/B
│   │   ├── security/                Installed — Phase C/B
│   │   ├── zerotrust/               Installed — Phase D
│   │   ├── landingzone/             Installed — Phase B
│   │   ├── iam/                     Stub — future
│   │   ├── hybrid/                  Stub — future
│   │   ├── container/               Stub — future
│   │   └── dns/                     Stub — future
│   ├── ai_engine/                   Phase D — MCP-backed analysis
│   ├── diagram_engine/              Phase B — TOP PRIORITY
│   ├── report_engine/               Phase E
│   └── delivery_portal/             Phase F
├── tests/
│   ├── unit/                        6 test files, all passing
│   └── integration/                 Phase C stubs
├── documentation/
│   ├── architecture/
│   ├── design/
│   ├── client-packet/
│   └── development/
└── .github/
    ├── workflows/ci.yml             Runs unit tests on push/PR
    └── CODEOWNERS
```
