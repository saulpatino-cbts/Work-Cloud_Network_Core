---
name: azure-drawio-mcp-diagramming
description: |
  Author Azure network diagrams using draw.io's `azure2` icon library through
  the in-app MCP surface. Use this skill whenever a user asks for an Azure
  topology diagram (VNet, VWAN hub, NSG, ExpressRoute, Private Endpoint) and
  the deliverable should match the engagement's pinned visual style.
---

# azure-drawio-mcp-diagramming

This is a CNA-vendored adaptation of the public
[thomast1906/azure-drawio-mcp-diagramming](https://github.com/thomast1906)
skill, narrowed to the icon library pinned for this product (`azure2`) and
wired into the same-origin draw.io MCP surface that `cna-web` exposes at
`/api/drawio-mcp`.

## When to use

- Author a new Azure-only diagram from a textual brief.
- Refresh icons on an existing diagram after the shape catalog changes.
- Walk a user through choosing the correct shape (e.g. "VNet vs subnet vs
  VWAN hub") before placing it.

## Hard constraints

- `library` MUST be `azure2`. Never emit `azure`, `azure3`, or any
  third-party stencil. The route handler will drop them anyway.
- Style strings MUST come from `cna/diagram_engine/data/azure_shapes.json`
  or from a fresh `search_shapes` response. Hand-rolled `mxgraph.*` strings
  are forbidden.
- For new shape requests, call `search_shapes` first; if nothing matches,
  ask the user to confirm a substitute before adding to the catalog.

## Tool surface

| Tool | Where | Purpose |
|------|-------|---------|
| `search_shapes` | `POST /api/drawio-mcp/search_shapes` | Find styles by keyword |
| `create_diagram` | `POST /api/drawio-mcp/create_diagram` | Validate XML and get an embed URL |
| `health` / `icon_libs` | `GET /api/drawio-mcp/{...}` | Liveness + pinned-libs probe |

## Workflow

1. Confirm the diagram is Azure-only. If it mixes clouds, defer to the
   sibling `drawio` skill.
2. Inventory the resources the user wants to show. For each, call
   `search_shapes` with the resource keyword; pick the highest-scoring hit.
3. Compose the draw.io XML with the picked styles. Use container cells for
   VNets and child cells for subnets; mirror the layout constants in
   `cna/diagram_engine/drawio_generator.py` for visual consistency with
   automatically-generated diagrams.
4. POST the XML to `create_diagram` to validate and obtain the embed URL.
5. Present the embed URL in chat; the `DrawioViewer` React component renders
   it inline in deliverable pages.
