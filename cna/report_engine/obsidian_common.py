"""Shared helpers for the Obsidian renderers (BUILD-02).

Both the findings vault (`obsidian_vault.py`) and the network-flow beehive
(`beehive.py`) build the same kind of artifact — a folder of linked Markdown
notes, zipped — so the slug / wiki-link / front-matter / write / zip machinery
lives here and is imported by both. No behavior change from the Phase 1
originals; this is an extraction so the two renderers do not duplicate it.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path


def slug(value: str, *, fallback: str = "item") -> str:
    """Turn an arbitrary id/name into a safe, stable note filename stem.

    Obsidian wiki-links reference the stem, so it must be deterministic and
    collision-resistant without leaking anything unexpected. Non-alphanumerics
    become hyphens; runs collapse; the result is trimmed and lower-cased.
    """
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip())
    text = re.sub(r"-{2,}", "-", text).strip("-._").lower()
    return text or fallback


def wikilink(stem: str, label: str | None = None) -> str:
    """An Obsidian wiki-link. `[[stem]]` or `[[stem|label]]`."""
    if label and label != stem:
        return f"[[{stem}|{label}]]"
    return f"[[{stem}]]"


def yaml_scalar(value: str) -> str:
    """Quote a YAML scalar safely (front-matter values may contain colons)."""
    v = (value or "").replace('"', '\\"')
    return f'"{v}"'


def write_note(path: Path, lines: list[str]) -> None:
    """Write a note's lines to `path`, creating parent dirs; trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def zip_tree(tree_dir: Path, zip_path: Path) -> Path:
    """Zip `tree_dir` into `zip_path`, entries rooted at the tree's own folder."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(tree_dir.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(tree_dir.parent))
    return zip_path
