# drawio-mcp (in-app)

Same-origin Draw.io tool surface co-located with `cna-web`. Exposes a REST
contract that mirrors the public Draw.io MCP App Server's tool shapes:

- `POST /api/drawio-mcp/search_shapes` → `{ query, limit? }`
- `POST /api/drawio-mcp/create_diagram` → `{ xml, name? }`
- `GET  /api/drawio-mcp/health`        → liveness probe
- `GET  /api/drawio-mcp/icon_libs`     → returns the pinned allow-list

The Python worker calls this surface via
`cna.ai_engine.mcp_client.drawio_mcp_client.DrawioMCPClient`.

## Icon library pinning (triple-enforced)

1. `shape-index.json` is filtered to `mxgraph.(azure2|aws4).*` at build time
   (see `scripts/filter-shape-index.mjs`).
2. The route handler re-filters every `search_shapes` result through
   `ALLOWED_LIBS` before returning.
3. The Python client re-filters again before returning to callers.

To switch libraries (e.g. add `azure3` when it ships):
- update `ALLOWED_LIBS` in `allow-list.ts`
- update `ALLOWED_LIBS` in `cna/ai_engine/mcp_client/drawio_mcp_client.py`
- update the regex in `scripts/filter-shape-index.mjs`
- rebuild the cna-web image
