"""Phase E — Obsidian Vault Renderer (BUILD-02, phase 1).

Renders a FindingsReport as an Obsidian vault: a folder of linked Markdown
notes that opens as a knowledge graph. An engineer (or the customer) can click
from a finding to the resources it affects to the framework it maps to, instead
of reading a flat PDF.

Design (see .kiro/specs/obsidian-second-brain/):
  - One note per finding, per affected resource, per recommendation, per
    framework, plus a README entry note. Notes wiki-link to each other so
    Obsidian builds the backlink graph automatically.
  - Front-matter (YAML) on finding notes carries severity, cloud, domain, and
    framework mappings for Obsidian's properties/search.
  - Observed facts and recommendations are kept in separate sections (DD-002:
    the Finding schema separates observed_state from recommendations; the vault
    preserves that distinction).
  - Plain Markdown only — no required Obsidian plugin.
  - Absorbs the Phase E knowledge-transfer package: the README is the
    how-to-read guide and the framework notes are the framework links per
    finding (knowledge_transfer.py stub is superseded by this).
  - Self-contained like HtmlPreviewRenderer: needs no PDF toolchain and no
    network. Output is a vault folder plus a .zip of it for delivery.

Isolation (R3): the renderer only reads the FindingsReport passed to it and
writes under the output_path the pipeline gives it (the engagement's own
deliverables dir). It has no path to any other engagement's data.

Safety (R6): no secret or credential is ever written; cost figures keep their
[VERIFY] marker.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cna.core.findings_schema import Finding, FindingSeverity, FindingsReport
from cna.report_engine.obsidian_common import slug as _slug
from cna.report_engine.obsidian_common import wikilink as _wikilink
from cna.report_engine.obsidian_common import write_note as _write_note
from cna.report_engine.obsidian_common import yaml_scalar as _yaml_scalar
from cna.report_engine.obsidian_common import zip_tree as _zip_tree

logger = logging.getLogger("cna.report.obsidian")

# Folder names inside the vault.
_FINDINGS_DIR = "Findings"
_RESOURCES_DIR = "Topology"
_RECS_DIR = "Recommendations"
_FRAMEWORKS_DIR = "Frameworks"

_SEVERITY_ORDER = {
    FindingSeverity.CRITICAL: 0,
    FindingSeverity.HIGH: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 3,
    FindingSeverity.INFORMATIONAL: 4,
}


class ObsidianVaultRenderer:
    """Renders a FindingsReport as an Obsidian vault folder, then zips it.

    Matches the renderer contract used by RenderPipeline: a `render(report,
    output_path, ...)` method. `output_path` is the path of the .zip to
    produce; the vault folder is written next to it (same stem, no extension)
    and then archived into the zip.
    """

    def render(
        self,
        report: FindingsReport,
        output_path: Path,
        *,
        topology: object | None = None,
        diagrams: list[Path] | None = None,
    ) -> Path:
        """Build the vault and zip it. Returns the zip path.

        Args:
            report: the reviewed FindingsReport.
            output_path: path of the .zip to write (e.g. <id>_vault_<ts>.zip).
            topology: optional topology object for richer resource notes
                (phase 1 does not require it; resource notes are derived from
                findings' affected_resources when topology is absent).
            diagrams: optional list of Mermaid/diagram files to embed under
                _attachments/diagrams/.
        """
        output_path = Path(output_path)
        vault_dir = output_path.with_suffix("")  # folder next to the zip
        vault_dir.mkdir(parents=True, exist_ok=True)

        # Collect the entities we will cross-link.
        resource_ids = self._collect_resource_ids(report)
        frameworks = self._collect_frameworks(report)

        self._write_readme(vault_dir, report, frameworks)
        self._write_finding_notes(vault_dir, report)
        self._write_resource_notes(vault_dir, report, resource_ids)
        self._write_recommendation_notes(vault_dir, report)
        self._write_framework_notes(vault_dir, frameworks)
        self._embed_diagrams(vault_dir, diagrams)

        zip_path = self._zip_vault(vault_dir, output_path)
        logger.info("Obsidian vault written: %s (zipped: %s)", vault_dir, zip_path)
        return zip_path

    # ---------------------------------------------------------------- collect

    @staticmethod
    def _collect_resource_ids(report: FindingsReport) -> set[str]:
        ids: set[str] = set()
        for f in report.findings:
            if f.resource_id:
                ids.add(f.resource_id)
            ids.update(r for r in (f.affected_resources or []) if r)
        return ids

    @staticmethod
    def _collect_frameworks(report: FindingsReport) -> set[str]:
        names: set[str] = set()
        for f in report.findings:
            for m in f.framework_mappings or []:
                if m.framework:
                    names.add(m.framework)
        return names

    @staticmethod
    def _finding_stem(f: Finding, index: int) -> str:
        base = f.id or f.rule_id or f"finding-{index}"
        return _slug(str(base), fallback=f"finding-{index}")

    # ---------------------------------------------------------------- writers

    def _write_readme(self, vault_dir: Path, report: FindingsReport, frameworks: set[str]) -> None:
        """The entry note — doubles as the knowledge-transfer how-to-read guide."""
        lines: list[str] = []
        lines.append("# Cloud Network Assessment — Knowledge Vault")
        lines.append("")
        lines.append(f"- **Engagement:** `{report.engagement_id}`")
        lines.append(f"- **Generated:** {report.generated_at}")
        lines.append(f"- **Schema:** {report.schema_version}")
        lines.append("")
        lines.append("## How to read this vault")
        lines.append("")
        lines.append(
            "Open this folder in [Obsidian](https://obsidian.md). Every finding, resource and "
            "recommendation is its own note, linked to the others. Click a link, or open the "
            "graph view, to explore how they connect. You can also read any note in a plain text "
            "editor — it is all Markdown."
        )
        lines.append("")
        lines.append("## What is here")
        lines.append("")
        lines.append(
            f"- **Findings** ({report.total_count}) — one note each, in `{_FINDINGS_DIR}/`."
        )
        lines.append(f"- **Topology** — the resources findings affect, in `{_RESOURCES_DIR}/`.")
        lines.append(f"- **Recommendations** — how to fix each finding, in `{_RECS_DIR}/`.")
        lines.append(f"- **Frameworks** — the standards findings map to, in `{_FRAMEWORKS_DIR}/`.")
        lines.append("")
        lines.append("## Findings by severity")
        lines.append("")
        lines.append(f"- Critical: {report.critical_count}")
        lines.append(f"- High: {report.high_count}")
        lines.append(f"- Medium: {report.medium_count}")
        lines.append(f"- Low: {report.low_count}")
        lines.append("")
        if frameworks:
            lines.append("## Frameworks referenced")
            lines.append("")
            for fw in sorted(frameworks):
                lines.append(f"- {_wikilink(_slug(fw), fw)}")
            lines.append("")
        self._write(vault_dir / "README.md", lines)

    def _write_finding_notes(self, vault_dir: Path, report: FindingsReport) -> None:
        d = vault_dir / _FINDINGS_DIR
        d.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            enumerate(report.findings),
            key=lambda pair: _SEVERITY_ORDER.get(pair[1].severity, 99),
        )
        for index, f in ordered:
            stem = self._finding_stem(f, index)
            lines: list[str] = []
            # front-matter
            lines.append("---")
            lines.append("type: finding")
            lines.append(f"severity: {f.severity.value}")
            if f.platform:
                lines.append(f"cloud: {f.platform}")
            if f.category:
                lines.append(f"domain: {_yaml_scalar(f.category)}")
            if f.region:
                lines.append(f"region: {_yaml_scalar(f.region)}")
            fw_names = [m.framework for m in (f.framework_mappings or []) if m.framework]
            if fw_names:
                lines.append("framework:")
                for fw in fw_names:
                    lines.append(f"  - {_yaml_scalar(fw)}")
            lines.append("---")
            lines.append("")
            lines.append(f"# {f.title}")
            lines.append("")
            if f.description:
                lines.append(f.description)
                lines.append("")
            # Observed (facts only — DD-002)
            lines.append("## Observed")
            lines.append("")
            lines.append(f.observed_state.fact)
            if f.observed_state.evidence_ref:
                lines.append("")
                lines.append(f"_Evidence: {f.observed_state.evidence_ref}_")
            lines.append("")
            # Affected resources (wiki-links)
            affected = [r for r in (f.affected_resources or []) if r]
            if f.resource_id and f.resource_id not in affected:
                affected = [f.resource_id, *affected]
            if affected:
                lines.append("## Affected resources")
                lines.append("")
                for rid in affected:
                    lines.append(f"- {_wikilink(_slug(rid), rid)}")
                lines.append("")
            # Recommendations (kept distinct from observed)
            recs = list(f.recommendations or [])
            if recs or f.recommendation:
                lines.append("## Recommended")
                lines.append("")
                for rec in recs:
                    src = f" ({rec.source})" if rec.source else ""
                    lines.append(f"- {rec.text}{src}")
                    if rec.reference_url:
                        lines.append(f"  - {rec.reference_url}")
                if f.recommendation and not recs:
                    src = f" ({f.recommendation_source})" if f.recommendation_source else ""
                    lines.append(f"- {f.recommendation}{src}")
                lines.append("")
            # Cost (keep [VERIFY])
            if f.est_monthly_cost_usd is not None:
                lines.append("## Estimated cost impact")
                lines.append("")
                lines.append(
                    f"- ${f.est_monthly_cost_usd:,.2f}/month **[VERIFY]** (static estimate)"
                )
                lines.append("")
            # Framework links
            if fw_names:
                lines.append("## Frameworks")
                lines.append("")
                for fw in fw_names:
                    lines.append(f"- {_wikilink(_slug(fw), fw)}")
                lines.append("")
            self._write(d / f"{stem}.md", lines)

    def _write_resource_notes(
        self, vault_dir: Path, report: FindingsReport, resource_ids: set[str]
    ) -> None:
        d = vault_dir / _RESOURCES_DIR
        d.mkdir(parents=True, exist_ok=True)
        # which findings reference each resource -> backlinks
        for rid in sorted(resource_ids):
            stem = _slug(rid)
            referencing = [
                self._finding_stem(f, i)
                for i, f in enumerate(report.findings)
                if rid == f.resource_id or rid in (f.affected_resources or [])
            ]
            lines = [
                "---",
                "type: resource",
                f"resource_id: {_yaml_scalar(rid)}",
                "---",
                "",
                f"# {rid}",
                "",
            ]
            if referencing:
                lines.append("## Findings affecting this resource")
                lines.append("")
                for s in referencing:
                    lines.append(f"- {_wikilink(s)}")
                lines.append("")
            self._write(d / f"{stem}.md", lines)

    def _write_recommendation_notes(self, vault_dir: Path, report: FindingsReport) -> None:
        d = vault_dir / _RECS_DIR
        d.mkdir(parents=True, exist_ok=True)
        seen: dict[str, list[str]] = {}
        for i, f in enumerate(report.findings):
            fstem = self._finding_stem(f, i)
            for rec in f.recommendations or []:
                key = _slug(rec.text[:60]) if rec.text else ""
                if not key:
                    continue
                seen.setdefault(key, [])
                if fstem not in seen[key]:
                    seen[key].append(fstem)
                path = d / f"{key}.md"
                if not path.exists():
                    lines = ["---", "type: recommendation", "---", "", f"# {rec.text}", ""]
                    if rec.source:
                        lines.append(f"- Source: {rec.source}")
                    if rec.reference_url:
                        lines.append(f"- Reference: {rec.reference_url}")
                    lines.append("")
                    lines.append("## Resolves")
                    lines.append("")
                    self._write(path, lines)
        # append the resolves backlinks
        for key, fstems in seen.items():
            path = d / f"{key}.md"
            if path.exists():
                extra = "\n".join(f"- {_wikilink(s)}" for s in fstems) + "\n"
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(extra)

    def _write_framework_notes(self, vault_dir: Path, frameworks: set[str]) -> None:
        if not frameworks:
            return
        d = vault_dir / _FRAMEWORKS_DIR
        d.mkdir(parents=True, exist_ok=True)
        for fw in sorted(frameworks):
            lines = [
                "---",
                "type: framework",
                f"name: {_yaml_scalar(fw)}",
                "---",
                "",
                f"# {fw}",
                "",
                "Findings that map to this framework backlink here automatically "
                "(see the Obsidian backlinks pane).",
                "",
            ]
            self._write(d / f"{_slug(fw)}.md", lines)

    def _embed_diagrams(self, vault_dir: Path, diagrams: list[Path] | None) -> None:
        if not diagrams:
            return
        d = vault_dir / "_attachments" / "diagrams"
        d.mkdir(parents=True, exist_ok=True)
        for src in diagrams:
            src = Path(src)
            if src.exists():
                (d / src.name).write_bytes(src.read_bytes())

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _write(path: Path, lines: list[str]) -> None:
        _write_note(path, lines)

    @staticmethod
    def _zip_vault(vault_dir: Path, zip_path: Path) -> Path:
        return _zip_tree(vault_dir, zip_path)
