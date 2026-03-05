# Phase A — Devil's Advocate Critique & Gap Analysis

> Unfiltered. No fluff. Every real problem with what was built.

---

## 1. Core Models

### `findings_schema.py`
- `observed_state` is a free-text string. Nothing enforces format consistency.
  Two engineers will write it completely differently. Add a structured format spec or a validator.
- `data_confidence: str = "HIGH"` defaults to HIGH. That is backwards.
  Confidence should be EARNED, not assumed. Default should be UNKNOWN or LOW.
- `framework_mappings` is optional and defaults to empty. A finding with zero framework
  mappings is useless for a compliance-oriented deliverable. Make at least one required.
- `recommendation_source` is Optional[str]. A free text URL field. No validation,
  no enforcement that it actually points to an MCP server. Easily left null forever.
- No `region_group` field (us | emea | japan). Regional report generation will require
  a lookup layer that could have been avoided by including it here.
- No `affected_accounts` field. Multi-account findings have no home.

### `engagement.py`
- `status` is a plain string with a comment showing valid values.
  Nothing enforces those values. A typo like `"Initalized"` will silently pass.
  Use a `Literal` type or `Enum`.
- `review_complete: bool` is a single boolean. In a real engagement you review
  findings incrementally. One boolean means either nothing is reviewed or everything is.
  There is no partial review state, no per-finding review tracking at this level.
- `modules_installed` is a plain list of strings. Nothing links it to
  the actual module registry at runtime. It can contain module names that don't exist.
- `engagement_end_date` is Optional[str]. Should be `Optional[date]`.
  String dates break sorting and comparison.

### `escalation_engine.py`
- `_matches()` returns `False` unconditionally and is labeled Phase C.
  That means this entire engine is inert dead code right now.
  It gives false confidence that critical finding detection exists. It does not.
- The trigger lists are hardcoded Python lists in the source file.
  Adding a new trigger requires a code change and a deployment. Should be YAML config.
- No deduplication. If the same critical resource is evaluated twice, it fires twice.
  In a multi-account sweep this will spam the notifier.
- `notifier` is injected but never defined anywhere. No interface, no contract, no stub.
  It will be `None` in 100% of runs until Phase D.

### `discovery_coverage.py`
- `block_reasons` is a list with no schema. It will accumulate mixed-format strings
  from different discovery methods and be unparseable in reports.
- No timestamp on when the coverage report was generated.
  Stale coverage reports are indistinguishable from fresh ones.
- `calculate_coverage()` only counts accounts. Regions, services, and
  resource types are collected but never factored into the percentage.
  The reported percentage is misleading — 80% account success could mean
  0% of actual resources if every region was blocked.

### `deliverable_dependency.py`
- `gap_analysis`, `zero_trust_scorecard`, `risk_register`, `platform_findings`
  are referenced as dependency sources but NONE of them are defined anywhere
  in the codebase. They are strings pointing at concepts, not real objects.
- `get_stale_deliverables()` returns names. Nothing calls it, nothing acts on it.
  The staleness detection system has no consumer and no trigger. It is completely inert.

### `version_manager.py`
- `DocumentVersion.generated_by` is a free-text string. No enforcement that
  it is one of `ai-engine | human-review | manual`.
- Version bumping is a standalone function with no persistence. Calling
  `bump_version("1.0.0")` returns `"1.0.1"` and then it evaporates.
  Nothing stores it, nothing reads it. The versioning system does not version anything.

---

## 2. CLI Layer

- Every command prints a TODO string and exits. The CLI is a shell with no behavior.
  `cna init` does not create a directory, write a config file, or do anything at all.
  A new engineer picking this up cannot run a single meaningful command.
- `--regions` accepts a comma-separated string. It is never split, never validated,
  never mapped to the `us | emea | japan` group model used everywhere else.
  The first actual use will require rework.
- `cna discover azure` takes `--sp-id` and `--tenant` as CLI flags.
  That means credentials are in shell history and process listings.
  Should read from `.env` or Key Vault only. This is a security design flaw.
- `cna report` says it is "blocked until review complete" in a comment.
  The block is not implemented. Nothing reads `engagement.review_complete`.
  The gate that was called non-negotiable does not exist in code.
- No `--engagement-id` flag on most commands. Commands have no way to target
  a specific engagement. Everything assumes one engagement at a time.
- No `--dry-run` flag on any command. For a tool running against production cloud
  environments, this is a significant missing safety mechanism.
- No `--output-dir` flag. Output paths are hardcoded in comments or absent entirely.
- `cna module list` and `cna module install` are TODO. The module system
  described in the README does not function.

---

## 3. Modules

- Every module under `discovery/` is a file with one comment: `# TODO: Phase C`.
  The most critical part of the platform — actually collecting data — is entirely absent.
- `module.yaml` files list required permissions. There is no code that reads
  those permissions and validates them before discovery starts. The permissions
  lists could be wrong and nothing would catch it until a runtime API error.
- `depends_on` is declared in YAML but nothing in `registry.py` checks it.
  Installing `security` without `network` will silently succeed.
- `cna/modules/network/prompts/` contains text files.
  Nothing in the AI engine reads them. They are orphaned documentation.
- Zero Trust module has no discovery component. It depends on `network` and
  `security` but the scorer has no input data contract. What data does it score?
  Undefined.
- Landing Zone module depends on `network` but the `network` module has no
  landing zone data structures in its topology output. The dependency is circular
  in concept and undefined in implementation.

---

## 4. Diagram Engine (Phase B)

- Four files, all `# TODO`. Phase B is declared TOP PRIORITY but has zero implementation.
  This critique exists because Phase B starts NOW.
- No input data contract is enforced. `drawio_generator.py` has a docstring describing
  what it takes, but there is no Pydantic model for topology input.
  The generator and the discovery engine can diverge with no type-level warning.
- The export pipeline references `drawio CLI`, `cairosvg`, and `reportlab` but
  none of these are verified to be installed at container build time beyond graphviz/cairo
  in the Dockerfile. `drawio` desktop CLI is not in the Dockerfile at all.
- No diagram naming convention is defined. Will output files be named by account ID,
  region, timestamp, engagement slug? Undefined. Every diagram type will invent its own.
- No diagram versioning. If discovery runs twice, do diagrams get overwritten?
  Archived? Named with timestamps? Undefined.

---

## 5. Infrastructure & DevOps

- There is no actual Azure infrastructure defined anywhere.
  The README says "Vendor Cloud Backend: Your Azure subscription" but there is
  no Bicep, Terraform, or ARM template. The backend does not exist.
- No Key Vault integration exists. Secrets are expected from `.env`.
  In production, every secret should come from Key Vault. `.env` is dev-only
  and the code treats it as the primary mechanism.
- No Azure Storage client exists. `EngagementConfig` is a Pydantic model
  with no persistence layer. Engagements exist in memory only.
- The CI pipeline runs `pytest tests/unit/` but the tests do not actually
  install the package in the CI environment correctly. `pip install -e ".[dev]"`
  requires the `dev` extra to be defined in `pyproject.toml`. It is defined, but
  `ruff` and `pytest` are listed there while `ruff` is also called before tests.
  If `ruff` is not installed, CI fails before tests run.
- No CD pipeline. No container build and push to GHCR. No deployment automation.
  The Dockerfile exists but is never used by any automated process.
- No branch protection rules defined. `main` can be pushed to directly.
  The CODEOWNERS file exists but has no effect without branch protection.
- No `develop` branch created. The CI workflow references it but it does not exist.

---

## 6. Documentation

- `welcome-packet.md`, `environment-info-form.md`, and `permission-grant-guide.md`
  are marked Draft. They were described as finalized in session context but
  were pushed as drafts with placeholder notes. Actual finalized content is not in the repo.
- Design decisions DD-001 through DD-016 are all listed as Accepted.
  None have a date, an author, or an alternative considered.
  A decision log with no alternatives recorded is a changelog, not a decision log.
- `documentation/architecture/overview.md` describes the data flow as a clean linear pipeline.
  It does not document failure modes, retry behavior, partial discovery, or
  what happens when the AI engine is unavailable. Happy-path-only architecture docs
  give a false picture of the system.
- No runbook. No on-call guide. No "what do I do when X fails" documentation.
- No security documentation. No threat model. No data classification policy.
  For a tool that ingests client cloud topology data, this is a notable gap.
- No CHANGELOG.md. Commit messages are the only history.

---

## 7. Testing

- 6 unit tests cover 6 data models. Zero behavior is tested.
  There are no tests for the CLI, the module registry, the diagram engine,
  the report engine, or any integration between components.
- `test_escalation_engine.py` tests that the engine does NOT escalate.
  That is testing inert dead code. The tests will still pass after Phase C
  makes the engine functional — only if someone remembers to update them.
- No test fixtures. No factories. No shared test data.
  Every test that needs a `Finding` or `EngagementConfig` will re-implement
  construction from scratch, creating maintenance debt immediately.
- No coverage threshold. CI passes at 0% meaningful coverage.
- No integration test infrastructure. Tests are labeled integration but
  contain only `# TODO: Phase C`. There is no mock AWS/Azure layer,
  no localstack config, no VCR cassettes. Integration testing has no foundation.

---

## 8. Security

- `--sp-id` and `--external-id` as CLI flags expose secrets in shell history.
  This was noted above and bears repeating: it is a security flaw, not a convenience tradeoff.
- No input sanitization on any CLI parameter. `--client` is used as a slug
  and likely as a directory name. Path traversal via `../../../etc` is untested.
- The permission grant guide tells clients to attach `ReadOnlyAccess` (AWS managed) plus
  additional permissions. `ReadOnlyAccess` is an extremely broad policy.
  The actual minimum required permissions are listed per module in `module.yaml`
  but the guide doesn't reference them. A security-conscious client will push back.
- No credential rotation strategy documented.
- No audit log of what the tool accessed. The discovery engine will make
  hundreds of API calls against client infrastructure with no record kept on our side.

---

## Summary of What Phase A Actually Delivered

| Component | State |
|---|---|
| Data models | Defined, not enforced, not persisted |
| CLI | Wired, all commands no-op |
| Modules | Manifests only, no behavior |
| Diagram engine | 4 empty files |
| AI engine | 5 empty files |
| Report engine | 6 empty files |
| Delivery portal | 3 empty files |
| Tests | 6 model tests, 0 behavior tests |
| Infrastructure | 0 actual resources |
| Security | Multiple open issues |

Phase A is a well-organized skeleton. It is not a working system.
The value is in the structure and the design decisions being codified.
None of it runs. Phase B must produce the first functional code.
