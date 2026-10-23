# Requirements — Obsidian "beehive" network-flow map (BUILD-02)

**Status:** Revised 2026-10-23 per user direction. No implementation of the
revised scope yet (the earlier findings-vault Phase 1 shipped; see the note on
rework below).
**Tracked by:** issue [Core#72](https://github.com/saulpatino-cbts/Work-Cloud_Network_Core/issues/72).

## What the beehive actually is (corrected)

The Obsidian vault — the "beehive" — is a **network flow and mapping view**: it
shows **ports, IPs, networks, and the connectivity between them** as a navigable,
exportable graph. It is not primarily a findings knowledge base. The earlier
Phase 1 built finding/resource/recommendation notes; the real target is the
**network topology as a graph** — who talks to what, on which ports, across which
networks — that an engineer can open, explore, and export.

## Deployment model (corrects the whole design)

- This tool serves **exactly one customer** per appliance, always.
- That one customer may have **multiple subscriptions, tenants, or accounts** —
  and those belong together, in one unified view.
- **Two separate customers are never in one appliance.** Each customer deploys
  their own. So there is no cross-customer isolation problem; the design problem
  is the opposite — **unifying one customer's multiple subscriptions/tenants**.

## Requirements

### R1 — Beehive network-flow vault export
**As an** assessment engineer, **I want** to export the discovered network as an
Obsidian vault of linked notes centered on flow and mapping, **so that** I can
explore and present ports, IPs, networks, and their connections as a graph.

Acceptance criteria:
1. THE SYSTEM SHALL produce a vault whose primary structure is the **network
   graph**: one note per network (VPC/VNet/subnet), one per node/interface with
   its IPs, and the **edges** between them (peerings, routes, security-group /
   NSG allowances) expressed as wiki-links so Obsidian's graph view renders the
   connectivity.
2. EACH connection note SHALL record the **ports/protocols** allowed on that edge
   (from security groups / NSGs / NACLs) and the source/destination IPs or CIDRs.
3. THE vault SHALL be opt-in via `RenderOptions` (default off) and gated by the
   existing `DD-009` review gate, recorded in the `DeliverableManifest` as
   `format="obsidian"`, shipped as a zip. (Already true from the first build.)
4. THE vault SHALL embed the diagram-engine's Mermaid topology diagrams where
   available.

### R2 — Exportable model
**As an** engineer, **I want** the beehive in an exportable form, **so that** the
network map can leave the appliance and be opened elsewhere.

Acceptance criteria:
1. THE vault SHALL be a self-contained zip of plain Markdown that opens in any
   Obsidian install or text editor (already met).
2. THE connectivity SHALL also be available in a **machine-readable** form
   (e.g. a `graph.json` of nodes + edges + ports in the vault) so the map can be
   imported into other tooling, not only read by a human.

### R3 — Unify one customer's multiple subscriptions/tenants in one view
**As an** engineer assessing a customer with several subscriptions/tenants/
accounts, **I want** them shown as **one** network map, **so that** cross-
subscription connectivity (peering, transit, VPN between a customer's own
networks) is visible.

Acceptance criteria:
1. THE beehive SHALL render nodes/edges from **all** of the customer's discovered
   subscriptions/tenants/accounts in one graph, each node labeled with its source
   subscription/tenant/account id.
2. Cross-subscription/cross-account connections (e.g. an Azure VNet peering to
   another subscription's VNet, an AWS TGW attachment across accounts) SHALL be
   drawn as edges, not dropped.

### R4 — Honesty and safety (unchanged)
Acceptance criteria:
1. The graph shows **observed** connectivity only (DD-002) — configured
   allowances and discovered links, labeled as such; it does not assert live
   reachability unless that came from the Reachability Analyzer (BUILD-01 C6).
2. NO secret or credential is ever written into a note.

## Relationship to the batch offline import

R3 (unifying multiple subscriptions) is served in large part by the **batch
offline export/import** capability, specified separately in
`.kiro/specs/batch-offline-import/`: a subscription/tenant scanned offline can be
exported as a batch record and imported into the online appliance, after which it
appears in the beehive as if it had been discovered online. The beehive consumes
the unified topology; the import is what unifies it.

## What already shipped, and the decision (1=c — keep both modes)

Phase 1 shipped a **findings-oriented** vault (ObsidianVaultRenderer: finding/
resource/recommendation/framework notes), tested and working. Decision: **keep
both views as separate modes**, not replace one with the other.

- **Findings mode** (shipped) — the existing finding/resource/recommendation/
  framework vault. Unchanged.
- **Network-flow (beehive) mode** (new) — a network-graph vault: networks,
  nodes+IPs, connection edges with ports/protocols, plus a machine-readable
  `graph.json` (R2.2) and multi-source unification (R3).

Both modes reuse the same shipped plumbing — the slug/wiki-link/front-matter/zip
machinery, the pipeline wiring (`render_obsidian` → `format="obsidian"`), the
review gate — and are selected by a mode option. Nothing from Phase 1 is thrown
away; the beehive is a second renderer path alongside it.

## Out of scope

- Any cross-customer / multi-customer feature (the deployment model is one
  customer per appliance).
- Live two-way sync with a running Obsidian app.

## Decisions already made (2026-10-23)

- Beehive = network flow/mapping (ports/IPs/networks), exportable — **not** a
  findings knowledge base.
- Single customer per appliance; unify that customer's multiple subscriptions/
  tenants; cross-tenant isolation is a non-issue (handled by deployment).
- Both a human-readable vault and a machine-readable `graph.json`.
- Multi-subscription unification is delivered with the batch offline import.
