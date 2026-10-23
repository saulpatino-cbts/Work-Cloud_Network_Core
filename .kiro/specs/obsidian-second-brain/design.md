# Design — Obsidian beehive (BUILD-02, dual-mode)

**Status:** Draft for review. No implementation of the beehive mode yet (the
findings mode shipped in Phase 1).
**Requirements:** `requirements.md`. Decisions: 1=c (keep both modes).

## Overview

The Obsidian vault export supports **two modes**, selected by a `RenderOptions`
field:

- **findings** (shipped) — `ObsidianVaultRenderer` as built: finding/resource/
  recommendation/framework notes.
- **beehive** (new) — a network-flow map: networks, nodes+IPs, and the
  connection edges between them with ports/protocols; plus a machine-readable
  `graph.json`; unifying all of one customer's subscriptions/tenants/accounts.

Both modes share the shipped plumbing (slug, wiki-links, front-matter, zip,
pipeline wiring, review gate). The beehive is a second renderer that consumes
**topology**, where the findings renderer consumes a `FindingsReport`.

## Data source: topology, not findings

The beehive is built from the discovered topology, which the platform already
reassembles per customer from per-source checkpoints:
`EngagementStore.load_aws_topology()` → `AWSTopology` and
`load_azure_topology()` → `AzureTopology`. Because those reassemble from **all**
of a customer's checkpoints (every subscription/account), the beehive is
multi-source by construction (R3) — including sources added by the batch offline
import (BUILD-03).

The renderer takes a normalized graph derived from both clouds' topology so one
code path renders an AWS-only, Azure-only, or mixed estate.

## The normalized network graph

An internal `NetworkGraph` (nodes + edges), built from `AWSTopology` /
`AzureTopology`, is the single input the beehive renders and the exact shape of
`graph.json`:

```
Node:
  id            stable id (e.g. "aws:acct123:vpc-abc" / "azure:sub1:vnet-x")
  kind          "network" | "subnet" | "node" | "gateway" | "endpoint"
  name          display name
  source_id     subscription / tenant / account id (R3: attribution kept)
  cloud         "aws" | "azure"
  cidrs         list[str]
  ips           list[str]           (for interfaces/endpoints)
Edge:
  src, dst      node ids
  kind          "peering" | "route" | "sg-allow" | "nsg-allow" | "tgw" | "vpn" | "reachable"
  ports         list[str]           ("tcp/443", "udp/53", "-1/all")
  cidr          source/dest CIDR when the allowance is CIDR-based
  source_id     where the edge was observed
  observed      true (DD-002 — configured/discovered; "reachable" edges come
                only from BUILD-01 C6 Reachability Analyzer results)
```

Edge derivation (observed only, R4):
- **networks/subnets** → nodes; subnet-in-VPC/VNet → containment edges.
- **peerings** (AWS VPC peering, Azure VNet peering) → `peering` edges, including
  cross-subscription/cross-account ones (R3.2).
- **routes** (route tables, TGW route analysis from BUILD-01 C3) → `route`/`tgw`
  edges; blackholes labeled.
- **security groups / NSGs / NACLs** → `sg-allow`/`nsg-allow` edges carrying the
  **ports/protocols and CIDRs** (the core of "visibility of ports, IPs,
  networks", R1.2).
- **VPN / Direct Connect / ExpressRoute** → `vpn` edges.
- **Reachability Analyzer results** (BUILD-01 C6), when present → `reachable`
  edges, the only ones asserting live reachability (R4.1).

## Components

New file `cna/report_engine/beehive.py`:

```python
class NetworkGraph(BaseModel):          # nodes + edges, serializes to graph.json
    nodes: list[GraphNode]
    edges: list[GraphEdge]

def build_network_graph(aws: AWSTopology | None, azure: AzureTopology | None) -> NetworkGraph: ...

class BeehiveRenderer:
    def render(self, graph: NetworkGraph, output_path: Path) -> Path:
        # writes the vault tree + graph.json, then zips (reusing the Phase 1 zip helper)
```

Vault tree (beehive mode):
```
<engagement_id>-beehive/
├── README.md                     entry: counts, how to read the graph
├── Networks/<node-id>.md         VPC/VNet/subnet notes, CIDRs, wiki-links to members + peers
├── Nodes/<node-id>.md            interfaces/endpoints with their IPs
├── Connections/<edge-id>.md      one note per edge: src -> dst, ports/protocols, CIDRs, kind
├── graph.json                    the machine-readable NetworkGraph (R2.2)
└── _attachments/diagrams/        Mermaid topology from the diagram engine
```

The note writers reuse the shipped `_slug` / `_wikilink` / front-matter / `_write`
helpers (refactored out of `obsidian_vault.py` into a small shared
`obsidian_common.py` so both renderers import them — no duplication).

## Pipeline wiring

`RenderOptions` gains `obsidian_mode: str = "findings"` (`"findings"` |
`"beehive"` | `"both"`). In `RenderPipeline.run()` the existing
`render_obsidian` block dispatches on the mode:
- `findings` → the shipped `ObsidianVaultRenderer` (unchanged).
- `beehive` → load topology, `build_network_graph`, `BeehiveRenderer`.
- `both` → emit two deliverables (`format="obsidian"`, distinct labels
  "Obsidian Findings Vault" / "Obsidian Beehive").

The review gate still applies (it gates all rendering). The beehive needs
topology, so when topology is absent the pipeline logs and skips the beehive
rather than failing (a findings-only engagement still works).

## Multi-source unification (R3)

Because `load_aws_topology` / `load_azure_topology` already fold every
checkpoint into one `AWSTopology`/`AzureTopology`, `build_network_graph`
naturally spans all of a customer's sources. Each node/edge carries `source_id`
so the graph view can group or color by subscription/account, and
cross-subscription peerings/TGW/VPN become ordinary edges. Sources added by the
batch offline import (BUILD-03) are already in the checkpoint set by the time
the beehive runs, so they appear with no beehive-side special-casing.

## Testing strategy (synthetic fixtures only)

- `build_network_graph` from a synthetic AWS+Azure topology → expected nodes,
  edges, ports on sg/nsg edges, cross-source peering edge present.
- `BeehiveRenderer` → expected note tree, `graph.json` round-trips to the same
  NetworkGraph, wiki-link audit (every link resolves), zip contains graph.json.
- Pipeline: `obsidian_mode="both"` yields two obsidian manifest records;
  `"beehive"` with no topology skips cleanly; review gate still blocks unreviewed.
- Observed-only: no `reachable` edge exists unless a C6 result was supplied.

## Risks

- **Graph size** on a large estate — the vault could be thousands of notes. Edges
  are the volume; mitigate by one note per edge only for sg/nsg allowances that
  matter (dedupe identical allowances) and summarizing the rest in the network
  note. Confirm on real topology.
- **Shared-helper refactor** touches the shipped renderer — covered by the
  existing Phase 1 tests staying green.
