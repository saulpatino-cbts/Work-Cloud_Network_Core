"""Shape catalog — single source of truth for draw.io style strings.

Loads curated `azure_shapes.json` and `aws_shapes.json` at import time and
enforces the pinned-library allow-list. The legacy STYLE_* constants in
`drawio_generator` are now thin wrappers around `shape_style()` so a future
catalog refresh (e.g. via the in-app MCP `search_shapes` tool) requires no
code change.

Triple-enforced pinning (matches apps/cna-web/lib/drawio-mcp/allow-list.ts):
  1. Build-time filter on apps/cna-web/lib/drawio-mcp/shape-index.json
  2. Route handler re-filter on each search_shapes response
  3. THIS catalog re-validates every loaded style against ALLOWED_LIBS

If a style violates the allow-list it is dropped at load time with a warning;
callers fall back to the provided default.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("cna.diagram_engine.shape_catalog")

ALLOWED_LIBS: frozenset[str] = frozenset({"azure2", "aws4"})

_STYLE_PREFIX_RE = re.compile(r"shape=mxgraph\.([a-z0-9]+)\.", re.IGNORECASE)

_DATA_DIR = Path(__file__).parent / "data"


def _lib_of(style: str) -> str | None:
    m = _STYLE_PREFIX_RE.search(style or "")
    return m.group(1).lower() if m else None


def is_allowed_style(style: str) -> bool:
    lib = _lib_of(style)
    return lib is not None and lib in ALLOWED_LIBS


def _load(filename: str) -> dict[str, str]:
    path = _DATA_DIR / filename
    if not path.exists():
        logger.warning("shape catalog missing: %s", path)
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.error("shape catalog %s unreadable: %s", path, e)
        return {}
    if not isinstance(raw, dict):
        logger.error("shape catalog %s must be a JSON object", path)
        return {}
    clean: dict[str, str] = {}
    for key, style in raw.items():
        if not isinstance(style, str) or not is_allowed_style(style):
            logger.warning(
                "shape catalog %s: dropping '%s' — style outside ALLOWED_LIBS %s",
                path.name,
                key,
                sorted(ALLOWED_LIBS),
            )
            continue
        clean[key] = style
    return clean


_AZURE: dict[str, str] = _load("azure_shapes.json")
_AWS: dict[str, str] = _load("aws_shapes.json")


def shape_style(library: str, key: str, default: str = "") -> str:
    """Return a style string for (library, key) or `default` if not catalogued.

    `library` must be one of ALLOWED_LIBS; anything else returns `default`.
    """
    lib = library.lower()
    if lib not in ALLOWED_LIBS:
        return default
    table = _AZURE if lib == "azure2" else _AWS
    return table.get(key, default)


def catalog_snapshot() -> dict[str, dict[str, str]]:
    """Return a deep copy for tests / CI guardrails."""
    return {"azure2": dict(_AZURE), "aws4": dict(_AWS)}
