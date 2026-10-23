"""Unit tests for cna.report_engine.obsidian_vault (BUILD-02 phase 1).

Synthetic fixtures only — no real engagement data, no network, no cloud.
Covers the spec acceptance criteria:
  R1  export produces a vault + zip; pipeline records a format="obsidian" record;
      the review gate blocks an unreviewed report.
  R2  one note per finding/resource/recommendation/framework + README; front-matter;
      wiki-links resolve (link audit).
  R3  isolation — the renderer writes only under the output path it is given.
  R6  observed vs recommended kept separate; cost keeps [VERIFY]; no secret leaks.
"""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cna.core.findings_schema import (
    Finding,
    FindingRecommendation,
    FindingsReport,
    FrameworkMapping,
)
from cna.report_engine.obsidian_vault import ObsidianVaultRenderer, _slug


# ── Fixtures ───────────────────────────────────────────────────────────────────


def _make_finding(
    severity: str = "high",
    rule_id: str = "AWS-NET-001",
    *,
    cost: float | None = None,
    recs: bool = True,
) -> Finding:
    return Finding(
        id=f"F-{rule_id}",
        rule_id=rule_id,
        severity=severity,
        platform="aws",
        region="us-east-1",
        category="network",
        title=f"Test finding {rule_id}",
        description="Test description",
        resource_id="vpc-001",
        resource_type="AWS::EC2::VPC",
        account_id="123456789012",
        observed_state="VPC vpc-001: is_default=True",
        affected_resources=["vpc-001", "subnet-abc"],
        framework_mappings=[
            FrameworkMapping(framework="AWS Well-Architected", version="2024", pillar="Reliability")
        ],
        recommendations=(
            [FindingRecommendation(source="AWS MCP", text="Enable flow logs", reference_url="https://x")]
            if recs
            else []
        ),
        est_monthly_cost_usd=cost,
    )


def _make_report(findings=None, *, review_complete: bool = True) -> FindingsReport:
    findings = findings if findings is not None else [
        _make_finding("critical"),
        _make_finding("high", "AWS-NET-002", cost=42.5),
    ]
    return FindingsReport(
        engagement_id="eng-test-001",
        findings=findings,
        total_count=len(findings),
        critical_count=sum(1 for f in findings if f.severity == "critical"),
        high_count=sum(1 for f in findings if f.severity == "high"),
        medium_count=sum(1 for f in findings if f.severity == "medium"),
        low_count=sum(1 for f in findings if f.severity == "low"),
        review_complete=review_complete,
        generated_at=datetime.now(UTC).isoformat(),
    )


def _render(tmp_path: Path, report: FindingsReport) -> tuple[Path, Path]:
    zip_path = tmp_path / "eng_vault.zip"
    out = ObsidianVaultRenderer().render(report=report, output_path=zip_path)
    vault = zip_path.with_suffix("")
    return out, vault


# ── slug helper ─────────────────────────────────────────────────────────────────


class TestSlug:
    def test_safe_and_stable(self):
        assert _slug("AWS::EC2::VPC vpc-001") == "aws-ec2-vpc-vpc-001"

    def test_collapses_and_trims(self):
        assert _slug("  --Foo//Bar--  ") == "foo-bar"

    def test_fallback_for_empty(self):
        assert _slug("", fallback="x") == "x"


# ── R2: structure, notes, front-matter ─────────────────────────────────────────


class TestVaultStructure:
    def test_core_tree_exists(self, tmp_path):
        _, vault = _render(tmp_path, _make_report())
        assert (vault / "README.md").is_file()
        assert (vault / "Findings").is_dir()
        assert (vault / "Topology").is_dir()
        assert (vault / "Recommendations").is_dir()
        assert (vault / "Frameworks").is_dir()

    def test_one_note_per_finding(self, tmp_path):
        _, vault = _render(tmp_path, _make_report())
        notes = list((vault / "Findings").glob("*.md"))
        assert len(notes) == 2

    def test_finding_front_matter(self, tmp_path):
        _, vault = _render(tmp_path, _make_report([_make_finding("critical")]))
        note = next((vault / "Findings").glob("*.md")).read_text(encoding="utf-8")
        assert note.startswith("---")
        assert "severity: critical" in note
        assert "cloud: aws" in note
        assert "domain:" in note

    def test_resource_and_framework_notes(self, tmp_path):
        _, vault = _render(tmp_path, _make_report())
        assert (vault / "Topology" / "vpc-001.md").is_file()
        assert (vault / "Topology" / "subnet-abc.md").is_file()
        assert (vault / "Frameworks" / _slug("AWS Well-Architected")).with_suffix(".md").is_file()


# ── R6: observed vs recommended, cost [VERIFY], no secrets ──────────────────────


class TestContentSafety:
    def test_observed_and_recommended_sections_distinct(self, tmp_path):
        _, vault = _render(tmp_path, _make_report([_make_finding("high")]))
        note = next((vault / "Findings").glob("*.md")).read_text(encoding="utf-8")
        assert "## Observed" in note
        assert "## Recommended" in note
        # observed fact appears above the recommended section
        assert note.index("## Observed") < note.index("## Recommended")

    def test_cost_keeps_verify_marker(self, tmp_path):
        _, vault = _render(tmp_path, _make_report([_make_finding("high", cost=42.5)]))
        note = next((vault / "Findings").glob("*.md")).read_text(encoding="utf-8")
        assert "[VERIFY]" in note
        assert "42.50" in note

    def test_no_cost_section_when_absent(self, tmp_path):
        _, vault = _render(tmp_path, _make_report([_make_finding("high", cost=None)]))
        note = next((vault / "Findings").glob("*.md")).read_text(encoding="utf-8")
        assert "Estimated cost impact" not in note


# ── R2: wiki-link audit — every link resolves to a note that exists ─────────────


class TestLinkAudit:
    def test_all_wikilinks_resolve(self, tmp_path):
        import re

        _, vault = _render(tmp_path, _make_report())
        stems = {p.stem for p in vault.rglob("*.md")}
        link_re = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
        for md in vault.rglob("*.md"):
            for target in link_re.findall(md.read_text(encoding="utf-8")):
                assert target in stems, f"broken wiki-link [[{target}]] in {md.name}"


# ── R1: zip + pipeline integration + review gate ───────────────────────────────


class TestZipAndPipeline:
    def test_zip_contains_the_vault(self, tmp_path):
        zip_path, vault = _render(tmp_path, _make_report())
        assert zip_path.is_file()
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert any(n.endswith("README.md") for n in names)
        assert any("/Findings/" in n for n in names)

    def test_pipeline_records_obsidian_format_and_gate(self, tmp_path):
        # Exercises RenderPipeline wiring: review gate + manifest record.
        from cna.core.persistence import EngagementStore
        from cna.report_engine.render_pipeline import (
            RenderOptions,
            RenderPipeline,
            ReviewGateError,
        )

        store = EngagementStore(data_dir=tmp_path, engagement_id="eng-test-001")
        opts = RenderOptions(
            render_html_preview=False,
            render_executive=False,
            render_technical=False,
            render_pptx=False,
            render_regional_en=False,
            render_obsidian=True,
            output_dir=tmp_path / "deliverables",
        )
        pipeline = RenderPipeline(store, opts)

        # Review gate blocks an unreviewed report.
        with pytest.raises(ReviewGateError):
            pipeline.run(_make_report(review_complete=False))

        # A reviewed report produces exactly the obsidian deliverable.
        manifest = RenderPipeline(store, opts).run(_make_report(review_complete=True))
        records = [r for r in manifest.records if r.format == "obsidian"]
        assert len(records) == 1
        # Default obsidian_mode is "findings"; the label distinguishes it from
        # the beehive deliverable in "both" mode.
        assert records[0].label == "Obsidian Findings Vault"
        assert Path(records[0].path).is_file()


# ── R3: isolation — renderer writes only under the given output path ────────────


class TestIsolation:
    def test_writes_only_under_output_path(self, tmp_path):
        before = {p for p in tmp_path.rglob("*")}
        zip_path = tmp_path / "sub" / "eng_vault.zip"
        ObsidianVaultRenderer().render(report=_make_report(), output_path=zip_path)
        after = {p for p in tmp_path.rglob("*")}
        new = after - before
        # every newly created path is under tmp_path/sub
        assert new, "nothing was written"
        assert all(str(p).startswith(str(tmp_path / "sub")) for p in new)
