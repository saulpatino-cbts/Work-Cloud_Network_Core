# Tasks — Obsidian second brain (BUILD-02)

**Status:** Draft for review. No implementation yet.
**Requirements:** `requirements.md`. **Design:** `design.md`.

Phase 1 (export, R1–R4) is implementable now. Phase 2 (AI brain, R5) is gated on a privacy review
and is listed but not started.

## Phase 1 — Vault export

- [x] 1. Renderer `cna/report_engine/obsidian_vault.py` — `ObsidianVaultRenderer.render(report,
  output_path, *, topology=None, diagrams=None)`, matching the renderer contract. _(R1)_
  - [x] 1.1 `_slug` helper (stable, collision-free, secret-free note filenames).

- [x] 2. Note writers:
  - [x] 2.1 Finding note — front-matter (severity, cloud, domain, framework) + Observed vs
    Recommended sections + wiki-links to `affected_resources`/frameworks; `[VERIFY]` on cost.
  - [x] 2.2 Resource note — id + backlinks to findings.
  - [x] 2.3 Recommendation note — text/source + links to resolved findings.
  - [x] 2.4 Framework note.
  - [x] 2.5 README entry note (also the knowledge-transfer how-to-read guide).
  - [x] 2.6 Diagram embedding into `_attachments/diagrams/` (optional `diagrams=` arg).

- [x] 3. Assemble the vault tree and zip it to `<engagement_id>_vault_<ts>.zip`. _(R1, R4)_

- [x] 4. Pipeline wiring: `render_obsidian` added to `RenderOptions`; render+manifest block in
  `RenderPipeline.run()` with `format="obsidian"`; review gate applies (verified by test). _(R1)_

- [x] 7. Absorbed `knowledge_transfer.py` into the vault (decision: README + Frameworks notes ARE
  the knowledge-transfer package; the stub now points at the renderer). _(R2)_

- [x] 6. Tests — `tests/unit/test_obsidian_vault.py`, 14 cases, all green (synthetic data only):
  structure, front-matter, observed-vs-recommended, cost `[VERIFY]`, wiki-link audit, zip, pipeline
  manifest record, review-gate block, isolation. _(R1, R2, R3, R6)_

- [x] 5. Delivery: added `.zip` → `application/zip` to the portal's `CONTENT_TYPES` so the vault
  uploads with a content type like every other deliverable; the portal already lists any manifest
  record generically and both deployers upload by path. Portal/deployer tests green. _(R4)_

- [x] 8. Docs: CHANGELOG `## [Unreleased] → Added` entry for the `obsidian` format. _(done)_

## Beehive mode — network-flow map (new; decision 1=c, keep both modes)

The cross-tenant privacy gate is REMOVED: one customer per appliance, so there is
no cross-customer surface (see `phase2-privacy-review.md`). The new work is the
network-flow beehive alongside the shipped findings vault.

- [x] 9. Shared helpers extracted to `obsidian_common.py` (slug, wikilink, yaml_scalar, write_note, zip_tree); both renderers import them. Phase 1 tests stayed green. _(shared plumbing)_
- [x] 10. `cna/report_engine/beehive.py`: `NetworkGraph`/`GraphNode`/`GraphEdge` + `build_network_graph(aws, azure)` with sg-allow/nsg-allow/peering/tgw/contains edges carrying ports/CIDRs + source_id; `reachable` only from C6; external-endpoint completion so links resolve. Observed-only (DD-002). _(R1, R3, R4)_
- [x] 11. `BeehiveRenderer.render` — Networks/Nodes/Connections notes + `graph.json`, zipped via the shared helper. _(R1, R2)_
- [x] 12. Pipeline: `RenderOptions.obsidian_mode` (`findings`|`beehive`|`both`); `_load_network_graph` from the store; skip-with-log when no topology; two records in `both`. _(R1)_
- [x] 13. Multi-source unification — `build_network_graph` spans all checkpoints; cross-account/cross-subscription peerings render as edges (tested). _(R3)_
- [x] 14. Tests — `tests/unit/test_beehive.py` (12): graph build (ports, cross-source, mixed-cloud), renderer tree + graph.json round-trip + wiki-link audit, pipeline modes (both / no-topology), observed-only. Findings tests still green. _(R1–R4)_
- [x] 15. CHANGELOG: beehive/both modes + graph.json. _(done)_

## Verification

- Findings mode "done" (SHIPPED): tasks 1–8, 87 tests green.
- Beehive mode "done" = tasks 9–15 complete, tests green, a beehive vault opens
  in Obsidian with a connected graph view, `graph.json` round-trips, and
  `obsidian_mode="both"` emits both vaults. Multi-source unification is covered by
  the batch-offline-import spec (BUILD-03) feeding the checkpoint set.
- No privacy-review gate (removed — single-customer deployment).
