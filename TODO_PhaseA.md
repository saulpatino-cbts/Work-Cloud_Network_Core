# Phase A — Devil's Advocate Critique

> Unfiltered. Every decision challenged. Every gap named.
> Fix these before calling Phase A truly done.

---

## Architecture Decisions

### DD-001: Delivery-only (no pre-sales)
You have no sales funnel documented anywhere. "Delivery-only" sounds like a scope decision but it's actually a business model decision with zero supporting logic. How does a client even get to the delivery stage if there's no pre-sales engagement? There's no pricing model, no SOW template, no engagement letter. You've built a platform with no defined entry point.

### DD-002: Observed state only, no assumptions
Good principle. Zero enforcement. The AI prompt templates in `prompts/vpc_analysis.txt` say "observed state only" as plain English text that GPT-4o will ignore the moment context from its training data bleeds in. There is no schema-level validation that a generated finding contains only data-grounded observations. `observed_state` is a required string field — a model could write "this is likely a dev environment" and pass validation. This is a policy, not a control.

### DD-003: Recommendations via MCP servers only
Awslabs/mcp and the Azure MCP server are not the same thing. The AWS MCP server is a collection of domain-specific servers — which ones exactly? Network? Security? Organizations? That decision is deferred to Phase D with no specification. If the wrong MCP server is invoked for a finding, recommendations will be wrong or irrelevant. No routing logic is defined beyond a `mcp_router.py` stub.

### DD-006: All regions enumerated dynamically
This will hit AWS API rate limits immediately at scale. A client with 50 accounts across 20 regions is 1,000+ describe calls per service per module. There is no throttling strategy, no exponential backoff spec, no pagination design, no concurrency model. "Dynamic" is not an architecture.

### DD-008: AI analyzes only our collected data
Same problem as DD-002. This is stated as a principle but `analysis_engine.py` is a stub. There is no data isolation boundary, no prompt injection protection, no validation that the data fed to the model hasn't been tampered with between discovery and analysis. Supply chain risk on your own pipeline is unaddressed.

### DD-009: Human review gate blocks report generation
`review_complete` is a boolean on a Pydantic model stored... where? In memory? On disk? In Azure Blob Storage? There is no persistence layer defined anywhere in Phase A. If the CLI process exits, `review_complete=True` is gone. The "gate" has no backend.

### DD-011: Landing zone = Mermaid docs, not IaC
This is fine as a scope boundary but it's not explained to the client anywhere meaningful. The welcome packet says "we do not deploy infrastructure" in passing. A client expecting IaC outputs will be surprised. Mermaid diagrams are not a deliverable most enterprise clients have asked for or will know how to use.

### DD-014: Executive PPTX auto-generated
Auto-generated PPTX from AI findings has a 100% chance of producing slides that look auto-generated. No human has reviewed a single PPTX template, slide structure, or brand guideline. "20 slides" is an arbitrary number with no content outline. This will be the first thing an executive rejects.

### DD-015: EN/JA language toggle
Machine translation of security findings into Japanese for enterprise clients is a liability. Technical terms like "Transit Gateway", "NSG", "Security Group" do not translate cleanly. There is no translation review process, no native speaker review gate, no glossary of preferred Japanese technical terms. Auto-translated security findings sent to a Japanese enterprise client is a credibility risk.

---

## What's Missing From Phase A

### No Persistence Layer
The single biggest gap. There is no storage model — no local file format spec, no Azure Blob Storage schema, no engagement state serialization. `EngagementConfig` is a Pydantic model with nowhere to go. `cna init` creates nothing. You cannot resume, audit, or version an engagement without this.

### No Authentication / Credential Management Model
`.env.example` lists credentials. That's it. There is no credential rotation strategy, no Key Vault integration pattern, no guidance on how the Docker container receives secrets at runtime. In production, a contractor runs `cna discover` on a client engagement — what credential workflow do they use? Unknown.

### No Engagement ID Strategy
`engagement_id` is a string. Who generates it? When? Is it a UUID? A slug + date? Is it used as the S3 prefix? The Azure Blob container path? The report filename? If two engineers run `cna init` for the same client, do they collide?

### No Concurrency or Locking Model
Two engineers could run `cna discover` against the same engagement simultaneously. There is no file lock, no Azure lease, no queue. Data corruption is guaranteed in a multi-operator workflow.

### No Error Taxonomy
There are no defined exception types anywhere. Discovery will encounter: auth failures, permission denied, rate limits, network timeouts, malformed API responses, partial results, and service unavailability. Every one of these needs a distinct error class and distinct handling behavior. Right now all of them would raise unhandled exceptions.

### No Logging Infrastructure
Every stub says `console.print(...)`. There is no structured logging setup — no log levels wired to `CNA_LOG_LEVEL`, no log file output, no correlation IDs per engagement, no audit log for the human review gate (who approved, when, from what IP). The human review gate is legally meaningless without an audit log.

### No Secret Scanning in CI
The CI pipeline runs pytest and ruff. It does not run `gitleaks`, `truffleHog`, or `detect-secrets`. An engineer could accidentally commit an AWS key and the pipeline would pass. Given this is a platform handling client cloud credentials, this is not optional.

### No Pre-commit Hooks
No `.pre-commit-config.yaml`. Engineers push directly to `main` with no local guardrails. Linting is `|| true` in CI — meaning it's decorative.

### No Branching Strategy Enforced
`develop` branch was discussed but never created. There are no branch protection rules on `main`. A direct push to `main` by anyone with repo access skips CI entirely if protection isn't enforced at the GitHub level.

### Module `depends_on` Not Enforced
`security` depends on `network`. If a user runs `cna analyze --module security` without having run network discovery first, what happens? Currently: nothing defined. The dependency graph in `module.yaml` is documentation, not enforcement.

### No Data Schema for Discovery Output
The diagram generation guide defines a "data contract" as an example dict in a Markdown file. That is not a contract. There is no Pydantic model, no JSON Schema, no versioned spec for what the discovery engine outputs and what the diagram engine consumes. Phase B will build diagrams against an undefined input contract and Phase C will produce output against an undefined output contract. They will not connect cleanly.

### No Diagram Engine Input Validation
`drawio_generator.py` is the top priority but there is nothing specifying what it accepts, what errors it raises on malformed input, what it does when a VPC has no subnets, when a TGW has 200 attachments, or when resource names contain XML-unsafe characters. These are guaranteed real-world inputs.

### The `output/` Directory Has No Structure Defined
`.gitignore` excludes `output/diagrams/` and `output/reports/` but neither directory exists and there is no spec for the path structure inside them. Phase B will generate files to an undefined location.

### No Rollback or Idempotency Design
`cna discover --resume` is a flag on the CLI with no backend. What constitutes "resumed"? What was checkpointed? Where? If discovery fails at account 47 of 50, which 47 are safely stored and which 3 need to be re-run?

### Test Coverage Is Superficial
All 6 unit tests test data models and pure functions. Zero tests touch the CLI layer. Zero tests validate that `module.yaml` files parse correctly. Zero tests assert that all installed modules have their `depends_on` modules also installed. Zero tests verify the `mcp_router` routes to the right server. The tests that exist are fine but they cover the least risky code in the repo.

### No Engagement Templates
There are no Jinja2 templates in the repo. `report_engine/` stubs reference Jinja2 but no templates exist. The PPTX deck references `python-pptx` but no slide template `.pptx` file exists. Phase E will start from scratch on these.

### No Client Data Handling Policy
This platform collects client cloud configuration data. Where does it live? How long? Who can access it? Is it encrypted at rest? Is it deleted after delivery? There is no data retention policy, no client data agreement template, no GDPR/SOC2 consideration documented anywhere. For an enterprise engagement platform, this is a legal gap.

---

## Summary Verdict

Phase A delivered a well-organized skeleton. The module structure is sound, the design decisions are directionally correct, and the core models reflect real product thinking. But the skeleton has no connective tissue: no persistence, no auth workflow, no error handling, no data contracts between phases, and no enforcement of the principles that are documented. Before Phase C ships, DD-002, DD-009, and the persistence layer must be real — or the platform will produce untrustworthy outputs with no audit trail and no recovery path.
