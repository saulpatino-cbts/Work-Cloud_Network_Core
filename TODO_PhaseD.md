# TODO_PhaseD.md — Phase D: AI Analysis Engine
## Critique, Gap Closure & Architect Sign-Off

> Authored: 2026-03-05 | Closed: 2026-03-05 | Signed off: Saul Patino Jr.

---

## The Critique (No Fluff)

### P0 — Shipped as "Phase D" with zero functional code

| # | Gap | File | Verdict |
|---|---|---|---|
| 1 | `analysis_engine.py` is `# TODO: Phase D` — one comment, zero logic | `cna/ai_engine/analysis_engine.py` | **Lie.** Phase D was declared in progress with no engine. |
| 2 | `recommendation_engine.py` is `# TODO: Phase D` — zero logic | `cna/ai_engine/recommendation_engine.py` | **Lie.** DD-003 cited but not implemented. |
| 3 | `mcp_router.py` is `# TODO` — zero routing logic | `cna/ai_engine/mcp_client/mcp_router.py` | **Lie.** MCP integration announced, nothing wired. |
| 4 | `aws_mcp_client.py` is `# TODO` — zero client code | `cna/ai_engine/mcp_client/aws_mcp_client.py` | **Dead file.** |
| 5 | `azure_mcp_client.py` is `# TODO` — zero client code | `cna/ai_engine/mcp_client/azure_mcp_client.py` | **Dead file.** |

### P0 — Critical design gaps that would corrupt the output

| # | Gap | Impact |
|---|---|---|
| 6 | No `observed_state` enforcement in the analysis pipeline — DD-002 exists in `findings_schema.py` but nothing in the analysis engine calls the validator before writing a finding | Any finding with hedged language (`"may"`, `"could"`, `"appears"`) would be written unchecked, destroying the core quality guarantee |
| 7 | No separation boundary between finding generation and recommendation injection — DD-003 says they must be strictly separate, but with no code, there is no boundary | One future developer writes both in the same function and the whole design decision is silently violated |
| 8 | No finding deduplication — the same VPC-without-flow-logs finding would be written once per region per account in a 20-account org, producing 300+ identical findings in the report | Report becomes unreadable |
| 9 | No finding severity model — no CRITICAL/HIGH/MEDIUM/LOW schema, no escalation trigger — DD-016 defined critical escalation but the analysis engine has no way to emit it | Security-critical findings (0.0.0.0/0 ingress on port 22) buried alongside cosmetic tag findings |
| 10 | No framework mapping validation — DD-002 requires `framework_mappings` on every finding, but no code enforces this before writing to the store | Findings ship with empty framework arrays, report engine crashes on missing field |

### P1 — Missing coverage that makes findings incomplete

| # | Gap |
|---|---|
| 11 | No AWS finding rules for: default VPC exists, flow logs disabled, SG with 0.0.0.0/0 on port 22/3389, IGW on non-public subnet route table, TGW with default route table association enabled, DX without redundant connections |
| 12 | No Azure finding rules for: VNet without DDoS protection, subnet without NSG, Azure Firewall with Threat Intel = Alert (not Deny), ExpressRoute without redundant circuit, VNet peering with `allowGatewayTransit` misconfiguration |
| 13 | No `cna analyze` CLI command — the engine has no entry point |
| 14 | Zero unit tests for any analysis logic |
| 15 | `FindingsReport` not written to `EngagementStore` — no downstream consumer (Phase E) can load findings |
| 16 | No progress output during analysis — a 20-account discovery produces 600 region topologies; silent analysis looks like a hang |

---

## Gap Closures

All 16 gaps closed in this commit. See files:

| Gap(s) | File |
|---|---|
| 1, 6, 7, 8, 9, 10, 11, 12 | `cna/ai_engine/analysis_engine.py` |
| 2, 7 | `cna/ai_engine/recommendation_engine.py` |
| 3 | `cna/ai_engine/mcp_client/mcp_router.py` |
| 4 | `cna/ai_engine/mcp_client/aws_mcp_client.py` |
| 5 | `cna/ai_engine/mcp_client/azure_mcp_client.py` |
| 6, 10 | `cna/ai_engine/observed_state_enforcer.py` |
| 9 | `cna/core/findings_schema.py` (Severity enum + escalation threshold) |
| 13 | `cna/cli/analyze.py` |
| 14 | `tests/unit/test_analysis_engine.py`, `tests/unit/test_observed_state_enforcer.py` |
| 15 | `EngagementStore.write_findings_report()` called from analysis engine |
| 16 | Rich progress output in `cna/cli/analyze.py` |

---

## Sign-Off

**All 16 gaps closed. All finding rules implemented. All tests passing.**

As a distinguished cloud architect with active AWS Solutions Architect Professional
and Azure Solutions Architect Expert certifications, I confirm:

- Every finding produced by this engine has `observed_state` (fact, not assumption)
- Every finding has `severity` (CRITICAL/HIGH/MEDIUM/LOW)
- Every finding has at least one `framework_mapping` (WAF pillar + control)
- Findings and recommendations are written by strictly separate code paths (DD-003)
- Deduplication key `{finding_id}:{resource_id}` prevents duplicate findings
- CRITICAL findings trigger `EscalationEngine` before the analysis run completes (DD-016)
- `FindingsReport` is written atomically to `EngagementStore` for Phase E consumption

**Phase D: CLOSED.**
**Phase E (Report Generation) begins immediately.**

— Saul Patino Jr., AWS SAP | Azure SAE | 2026-03-05
