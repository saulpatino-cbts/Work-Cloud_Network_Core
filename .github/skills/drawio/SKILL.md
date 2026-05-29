---
name: drawio
description: |
  General-purpose draw.io authoring skill. Use for multi-cloud diagrams
  (AWS + Azure in one canvas) or any diagram that crosses the boundaries of
  the cloud-specific siblings. Constrained to the pinned icon libraries
  `azure2` and `aws4`.
---

# drawio

CNA-vendored adaptation of the upstream `jgraph/drawio-mcp` skill CLI. The
upstream tooling targets a standalone MCP server; we run an equivalent REST
surface inside `cna-web` so authoring works without provisioning a separate
container or exposing the network edit port.

## When to use

- The diagram contains resources from more than one cloud, OR
- The user wants a generic system diagram that does not fit the
  Azure-only or AWS-only siblings, OR
- You are bulk-rebuilding an existing draw.io file and need to re-apply
  styles from the pinned catalog.

## Hard constraints

- Only `azure2` and `aws4` libraries are allowed. The route handler, the
  Python client, and the build-time filter all enforce this; the skill must
  not try to work around it.
- Every shape used MUST come from a `search_shapes` response or the bundled
  catalogs at `cna/diagram_engine/data/{azure,aws}_shapes.json`.

## Quick recipe

1. `POST /api/drawio-mcp/icon_libs` (well, `GET`) to confirm the pinned
   set on the current cna-web build.
2. For each resource the user mentions, run `search_shapes` with a short
   keyword phrase. Choose the highest-scoring hit whose `library` matches
   the expected cloud.
3. Render the XML, then `POST /api/drawio-mcp/create_diagram` to validate
   and receive the viewer embed URL.

## Failure modes

- Empty `search_shapes` results → ask the user for a closer keyword or pick
  a generic container; never invent a `mxgraph.*` style.
- `create_diagram` rejects the payload → check the XML has both `<mxfile>`
  and `</mxfile>` and a valid `<mxGraphModel>` inside.
- MCP surface unreachable → the bundled `shape_catalog.py` still works
  offline; tell the user the rendered diagram is fine but the interactive
  studio is not currently up.
