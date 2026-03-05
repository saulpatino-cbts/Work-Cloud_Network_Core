# Design Decisions Log

All architectural and product decisions are recorded here.
Once accepted, a decision requires a new DD entry to change — not silent overrides.

| ID | Decision | Rationale | Status |
|---|---|---|---|
| DD-001 | Delivery-only platform (not pre-sales) | Focused scope, higher quality, justified price point | Accepted |
| DD-002 | Discovery = observed state only, no assumptions | Prevents AI hallucination contaminating findings | Accepted |
| DD-003 | Recommendations via official AWS/Azure MCP servers | Vendor-authoritative guidance, not our opinion | Accepted |
| DD-004 | Client one-pager + permission grant guide upfront | Removes blockers before engagement starts | Accepted |
| DD-005 | Discovery gaps surfaced in final reports | Transparency and data quality credibility | Accepted |
| DD-006 | All active regions enumerated dynamically | No hardcoded region lists that go stale | Accepted |
| DD-007 | Logging is client responsibility | We never touch client logging configs | Accepted |
| DD-008 | AI analyzes only our collected data | AI never connects directly to client environment | Accepted |
| DD-009 | Human review gate blocks report generation | No AI-only reports delivered — ever | Accepted |
| DD-010 | Diagram generation is TOP PRIORITY (Phase B) | First tangible deliverable, high client value | Accepted |
| DD-011 | Landing zone = Mermaid detail docs, not IaC | We present and recommend, we do not deploy | Accepted |
| DD-012 | Document versioning: manual + automatic | Audit trail for iterative engagement deliverables | Accepted |
| DD-013 | Deliverable dependency graph | Stale detection prevents outdated reports | Accepted |
| DD-014 | Executive PPTX deck auto-generated | Reduces post-engagement effort | Accepted |
| DD-015 | Static site EN/JA toggle + PDF export per language | Japan region requirement | Accepted |
| DD-016 | Three critical risks enforced in code | Policy without enforcement is decorative | Accepted |
