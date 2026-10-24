"""Phase E — Render Pipeline.

Orchestrates all report output formats for an engagement.
This is the single entry point for all rendering — no report module
calls a renderer directly.

Design contracts enforced here:
  DD-009: review_complete gate — raises ReviewGateError if FindingsReport
          has not been reviewed. This check happens BEFORE any rendering.
  DD-013: Deliverable staleness — manifest records source checksum;
          Phase F portal warns if topology has changed since last render.
  DD-017: All output filenames include engagement_id + ISO timestamp.
          Two renders of the same engagement produce distinct, traceable files.

Output written to: engagements/{engagement_id}/deliverables/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cna.core.findings_schema import FindingsReport
from cna.core.persistence import EngagementStore
from cna.report_engine.deliverable_manifest import DeliverableManifest, DeliverableRecord

logger = logging.getLogger("cna.report.pipeline")


class ReviewGateError(RuntimeError):
    """Raised when FindingsReport.review_complete is False (DD-009)."""

    pass


class JaReviewGateError(RuntimeError):
    """Raised when JA regional report is requested but ja_review_complete is False (DD-015)."""

    pass


@dataclass
class RenderOptions:
    render_executive: bool = True
    render_technical: bool = True
    render_pptx: bool = True
    render_html_preview: bool = True
    render_regional_en: bool = True
    render_regional_ja: bool = False  # requires ja_review_complete=True
    render_encyclopedia: bool = False  # six-chapter encyclopedia report (Phase D)
    encyclopedia_edition: str = "expanded"  # "condensed" | "expanded"
    render_obsidian: bool = False  # Obsidian vault (BUILD-02); off by default
    obsidian_mode: str = "findings"  # "findings" | "beehive" | "both"
    ja_review_complete: bool = False
    skip_pdf: bool = False  # HTML-only mode, no PDF toolchain required
    output_dir: Path | None = None  # defaults to store deliverables dir


class RenderPipeline:
    """Renders all engagement deliverables from a reviewed FindingsReport."""

    def __init__(self, store: EngagementStore, options: RenderOptions | None = None):
        # DeliverableManifest is a dataclass, so it does not validate: a None
        # engagement_id would be written into the manifest as null rather than
        # rejected. A pipeline that cannot identify its engagement cannot
        # produce a valid manifest, so require it here (TODO.md T-410).
        if store.engagement_id is None:
            raise ValueError(
                "RenderPipeline requires an EngagementStore bound to an "
                "engagement_id; construct it with EngagementStore(engagement_id=...)."
            )
        self.store = store
        self.engagement_id: str = store.engagement_id
        self.opts = options or RenderOptions()
        self._manifest = DeliverableManifest(engagement_id=self.engagement_id)

    def _output_dir(self) -> Path:
        # The default must follow the store's data_dir (it was previously a
        # hardcoded ./engagements, which ignored `cna report --data-dir`).
        base = self.opts.output_dir or (
            self.store.engagement_dir(self.engagement_id) / "deliverables"
        )
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _timestamp(self) -> str:
        return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    def _filename(self, label: str, ext: str) -> str:
        return f"{self.engagement_id}_{label}_{self._timestamp()}.{ext}"

    # ---------------------------------------------------------------- gate check

    def _enforce_review_gate(self, report: FindingsReport) -> None:
        """DD-009: Block all rendering if findings have not been reviewed."""
        if not report.review_complete:
            raise ReviewGateError(
                f"Engagement {self.engagement_id}: FindingsReport has "
                f"review_complete=False. Run `cna review complete "
                f"--engagement-id {self.engagement_id}` before generating reports."
            )

    def _load_network_graph(self):
        """Build the beehive NetworkGraph from the engagement's topology.

        Returns None when neither an AWS nor an Azure topology exists for the
        engagement (a findings-only engagement), so the pipeline can skip the
        beehive without failing. Spans every discovery checkpoint the store
        holds, so one customer's multiple subscriptions/accounts — including any
        added by the batch offline import — are unified in one graph.
        """
        from cna.report_engine.beehive import build_network_graph

        aws = azure = None
        try:
            aws = self.store.load_aws_topology(self.engagement_id)
        except FileNotFoundError:
            pass
        try:
            azure = self.store.load_azure_topology(self.engagement_id)
        except FileNotFoundError:
            pass
        if aws is None and azure is None:
            return None
        return build_network_graph(aws=aws, azure=azure)

    def _enforce_ja_gate(self) -> None:
        """DD-015: Block JA report if native speaker review not complete."""
        if not self.opts.ja_review_complete:
            raise JaReviewGateError(
                f"Engagement {self.engagement_id}: JA regional report requested "
                f"but ja_review_complete=False. Complete native speaker review and set "
                f"--ja-review-complete flag."
            )

    # ---------------------------------------------------------------- run

    def run(self, report: FindingsReport) -> DeliverableManifest:
        """Execute the full render pipeline. Returns completed DeliverableManifest.

        Raises ReviewGateError if review_complete=False (DD-009).
        Raises JaReviewGateError if JA requested but ja_review_complete=False (DD-015).
        """
        # DD-009: Gate check FIRST — before any import or file creation
        self._enforce_review_gate(report)

        out = self._output_dir()
        engagement_id = self.engagement_id

        if self.opts.render_html_preview:
            from cna.report_engine.html_preview import HtmlPreviewRenderer

            renderer = HtmlPreviewRenderer()
            html_path = out / self._filename("preview", "html")
            renderer.render(report=report, output_path=html_path)
            self._manifest.add(
                DeliverableRecord(
                    label="HTML Preview",
                    path=str(html_path),
                    format="html",
                    lang="en",
                )
            )
            logger.info("[%s] HTML preview written: %s", engagement_id, html_path)

        if self.opts.render_executive and not self.opts.skip_pdf:
            from cna.report_engine.executive_report import ExecutiveReportRenderer

            renderer = ExecutiveReportRenderer()
            pdf_path = out / self._filename("executive", "pdf")
            renderer.render(report=report, output_path=pdf_path)
            self._manifest.add(
                DeliverableRecord(
                    label="Executive Report (PDF)",
                    path=str(pdf_path),
                    format="pdf",
                    lang="en",
                )
            )
            logger.info("[%s] Executive PDF written: %s", engagement_id, pdf_path)

        if self.opts.render_technical and not self.opts.skip_pdf:
            from cna.report_engine.technical_report import TechnicalReportRenderer

            renderer = TechnicalReportRenderer()
            pdf_path = out / self._filename("technical", "pdf")
            renderer.render(report=report, output_path=pdf_path)
            self._manifest.add(
                DeliverableRecord(
                    label="Technical Report (PDF)",
                    path=str(pdf_path),
                    format="pdf",
                    lang="en",
                )
            )
            logger.info("[%s] Technical PDF written: %s", engagement_id, pdf_path)

        if self.opts.render_pptx:
            from cna.report_engine.presentation_deck import PresentationDeckBuilder

            builder = PresentationDeckBuilder()
            pptx_path = out / self._filename("deck", "pptx")
            builder.build(report=report, output_path=pptx_path)
            self._manifest.add(
                DeliverableRecord(
                    label="Presentation Deck (PPTX)",
                    path=str(pptx_path),
                    format="pptx",
                    lang="en",
                )
            )
            logger.info("[%s] PPTX deck written: %s", engagement_id, pptx_path)

        if self.opts.render_encyclopedia and not self.opts.skip_pdf:
            from cna.report_engine.encyclopedia_report import EncyclopediaReportRenderer

            edition = self.opts.encyclopedia_edition
            renderer = EncyclopediaReportRenderer(edition=edition)
            pdf_path = out / self._filename(f"encyclopedia_{edition}", "pdf")
            renderer.render(
                findings=report.findings,
                output_path=pdf_path,
                engagement={
                    "engagement_id": report.engagement_id,
                    "generated_at": report.generated_at,
                },
            )
            self._manifest.add(
                DeliverableRecord(
                    label=f"Encyclopedia {edition.capitalize()} (PDF)",
                    path=str(pdf_path),
                    format="pdf",
                    lang="en",
                )
            )
            logger.info("[%s] Encyclopedia %s written: %s", engagement_id, edition, pdf_path)

        if self.opts.render_regional_en and not self.opts.skip_pdf:
            from cna.report_engine.regional_report import RegionalReportRenderer

            renderer = RegionalReportRenderer(lang="en")
            pdf_path = out / self._filename("regional_en", "pdf")
            renderer.render(report=report, output_path=pdf_path)
            self._manifest.add(
                DeliverableRecord(
                    label="Regional Report EN (PDF)",
                    path=str(pdf_path),
                    format="pdf",
                    lang="en",
                )
            )
            logger.info("[%s] Regional EN written: %s", engagement_id, pdf_path)

        if self.opts.render_regional_ja:
            # DD-015: JA gate check before any JA rendering
            self._enforce_ja_gate()
            from cna.report_engine.regional_report import RegionalReportRenderer

            renderer = RegionalReportRenderer(lang="ja")
            pdf_path = out / self._filename("regional_ja", "pdf")
            renderer.render(report=report, output_path=pdf_path)
            self._manifest.add(
                DeliverableRecord(
                    label="Regional Report JA (PDF)",
                    path=str(pdf_path),
                    format="pdf",
                    lang="ja",
                )
            )
            logger.info("[%s] Regional JA written: %s", engagement_id, pdf_path)

        if self.opts.render_obsidian:
            # Obsidian vault (BUILD-02). Needs no PDF toolchain, so it is not
            # gated by skip_pdf. Two modes: the findings vault, the network-flow
            # beehive, or both. Each produces a zip the portal ships.
            mode = self.opts.obsidian_mode
            if mode in ("findings", "both"):
                from cna.report_engine.obsidian_vault import ObsidianVaultRenderer

                zip_path = out / self._filename("vault", "zip")
                ObsidianVaultRenderer().render(report=report, output_path=zip_path)
                self._manifest.add(
                    DeliverableRecord(
                        label="Obsidian Findings Vault",
                        path=str(zip_path),
                        format="obsidian",
                        lang="en",
                    )
                )
                logger.info("[%s] Obsidian findings vault written: %s", engagement_id, zip_path)
            if mode in ("beehive", "both"):
                graph = self._load_network_graph()
                if graph is None:
                    logger.info(
                        "[%s] Beehive requested but no topology found — skipping.", engagement_id
                    )
                else:
                    from cna.report_engine.beehive import BeehiveRenderer

                    zip_path = out / self._filename("beehive", "zip")
                    BeehiveRenderer().render(graph, zip_path)
                    self._manifest.add(
                        DeliverableRecord(
                            label="Obsidian Beehive",
                            path=str(zip_path),
                            format="obsidian",
                            lang="en",
                        )
                    )
                    logger.info("[%s] Obsidian beehive written: %s", engagement_id, zip_path)

        # Write manifest to store for Phase F portal
        self.store.write_deliverable_manifest(
            engagement_id=engagement_id,
            manifest=self._manifest.to_dict(),
        )
        logger.info(
            "[%s] Deliverable manifest written: %d items",
            engagement_id,
            len(self._manifest.records),
        )
        return self._manifest
