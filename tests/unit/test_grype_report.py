"""Tests for scripts/ci/grype_report.py (TODO.md T-719).

This script is the policy decision of workflow 390: a fixable HIGH or CRITICAL
finding fails the job, everything else is reported, and a report that is missing,
empty or malformed is an error rather than a clean image. Each case runs the real
entry point as a subprocess on a Grype-shaped JSON report built here.
"""

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "grype_report.py"
IMAGE = "docker.io/acme-org/cna@sha256:" + "ab" * 32


def base_env() -> dict[str, str]:
    """The minimum environment a Python subprocess needs, on any platform."""
    return {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}


def match(
    vuln_id: str = "CVE-2026-0001",
    severity: str = "High",
    state: str = "fixed",
    fix_versions: list[str] | None = None,
    package: str = "libssl3",
    version: str = "3.5.7-1",
    package_type: str = "deb",
) -> dict:
    """One Grype match in the shape of `grype -o json`."""
    return {
        "vulnerability": {
            "id": vuln_id,
            "severity": severity,
            "fix": {
                "state": state,
                "versions": ["3.5.8-1"] if fix_versions is None else fix_versions,
            },
        },
        "relatedVulnerabilities": [],
        "matchDetails": [],
        "artifact": {"name": package, "version": version, "type": package_type},
    }


def report(*matches: dict, **extra: object) -> dict:
    return {
        "matches": list(matches),
        "source": {
            "type": "image",
            "target": {
                # stereoscope spells Docker Hub index.docker.io in the recorded repo digest.
                "repoDigests": ["index.docker.io/" + IMAGE.split("/", 1)[1]],
            },
        },
        "descriptor": {"name": "grype", "version": "0.118.0"},
        **extra,
    }


def run_report(
    tmp_path: Path,
    document: object,
    *flags: str,
    name: str = "cli",
    raw: str | None = None,
) -> tuple[subprocess.CompletedProcess, str]:
    path = tmp_path / "grype.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    elif document is not None:
        path.write_text(json.dumps(document), encoding="utf-8")
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--report", str(path), "--name", name, "--image", IMAGE]
        + list(flags),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT.parent,
        env={**base_env(), "GITHUB_STEP_SUMMARY": str(summary)},
    )
    return result, summary.read_text(encoding="utf-8") if summary.exists() else ""


class TestPolicy:
    @pytest.mark.parametrize("severity", ["High", "Critical"])
    def test_a_fixable_high_or_critical_finding_fails(self, tmp_path: Path, severity: str) -> None:
        result, summary = run_report(tmp_path, report(match(severity=severity)))

        assert result.returncode == 1, result.stdout
        assert "**FAIL**" in summary
        assert "::error title=Fixable HIGH+ vulnerabilities in cli::" in result.stdout

    @pytest.mark.parametrize("state", ["not-fixed", "wont-fix", "unknown", ""])
    def test_an_unfixable_high_finding_is_reported_but_passes(
        self, tmp_path: Path, state: str
    ) -> None:
        result, summary = run_report(
            tmp_path, report(match(severity="Critical", state=state, fix_versions=[]))
        )

        assert result.returncode == 0, result.stdout
        assert "**PASS**" in summary
        assert "CVE-2026-0001" in summary, "unfixable findings are still reported"
        assert "::error" not in result.stdout

    @pytest.mark.parametrize("severity", ["Medium", "Low", "Negligible", "Unknown"])
    def test_a_fixable_finding_below_the_threshold_passes(
        self, tmp_path: Path, severity: str
    ) -> None:
        result, summary = run_report(tmp_path, report(match(severity=severity)))

        assert result.returncode == 0, result.stdout
        assert "**PASS**" in summary

    def test_the_threshold_is_configurable(self, tmp_path: Path) -> None:
        high = report(match(severity="High"))
        medium = report(match(severity="Medium"))

        assert run_report(tmp_path, high, "--fail-on", "critical")[0].returncode == 0
        assert run_report(tmp_path, medium, "--fail-on", "medium")[0].returncode == 1
        assert run_report(tmp_path, medium, "--fail-on", "high")[0].returncode == 0

    def test_an_unknown_threshold_is_a_usage_error(self, tmp_path: Path) -> None:
        result, _ = run_report(tmp_path, report(), "--fail-on", "unknown")

        assert result.returncode == 2

    def test_severity_matching_is_case_insensitive_and_unrecognised_is_unknown(
        self, tmp_path: Path
    ) -> None:
        assert run_report(tmp_path, report(match(severity="HIGH")))[0].returncode == 1
        assert run_report(tmp_path, report(match(severity="critical")))[0].returncode == 1
        assert run_report(tmp_path, report(match(severity="catastrophic")))[0].returncode == 0

    def test_one_violation_among_many_findings_is_enough(self, tmp_path: Path) -> None:
        document = report(
            *[match(f"CVE-2026-{n:04d}", "Low", package=f"pkg{n}") for n in range(30)],
            match("CVE-2026-9999", "Critical", package="openssl"),
        )

        result, _ = run_report(tmp_path, document)

        assert result.returncode == 1
        assert "CRITICAL CVE-2026-9999 openssl 3.5.7-1 -> 3.5.8-1" in result.stdout


class TestUnusableReportIsNeverAPass:
    def test_a_missing_report_is_an_error(self, tmp_path: Path) -> None:
        result, _ = run_report(tmp_path, None)

        assert result.returncode == 2
        assert "cannot read the Grype report" in result.stdout

    @pytest.mark.parametrize("raw", ["", "   \n"])
    def test_an_empty_report_is_an_error(self, tmp_path: Path, raw: str) -> None:
        result, _ = run_report(tmp_path, None, raw=raw)

        assert result.returncode == 2
        assert "is empty" in result.stdout

    @pytest.mark.parametrize(
        "raw",
        [
            "not json",
            "[]",
            "{}",
            '{"matches": null}',
            '{"matches": "none"}',
            '{"matches": [1]}',
            '{"matches": [{}]}',
            '{"matches": [{"vulnerability": {"severity": "High"}, "artifact": {"name": "p"}}]}',
            '{"matches": [{"vulnerability": {"id": "CVE-1"}, "artifact": {}}]}',
        ],
    )
    def test_a_structurally_unexpected_report_is_an_error(self, tmp_path: Path, raw: str) -> None:
        result, _ = run_report(tmp_path, None, raw=raw)

        assert result.returncode == 2, result.stdout
        assert "::error title=Grype report unusable::" in result.stdout

    def test_a_report_with_no_findings_passes_but_warns(self, tmp_path: Path) -> None:
        result, summary = run_report(tmp_path, report())

        assert result.returncode == 0
        assert "::warning::" in result.stdout and "zero findings" in result.stdout
        assert "0 matches: confirm the vulnerability database was current" in summary


def each_order(tmp_path: Path, records: list[dict]):
    """Run the script once per ordering of `records`, each with its own summary file."""
    for index, ordering in enumerate(itertools.permutations(records)):
        run_dir = tmp_path / f"order-{index}"
        run_dir.mkdir()
        result, summary = run_report(run_dir, report(*ordering))
        yield ordering, result, summary


class TestDuplicateMatchesNeverHideAViolation:
    """Grype can list one vulnerability on one package more than once, with different
    severity or fix data (one record per data source). The verdict must not depend
    on which record comes first."""

    @pytest.mark.parametrize(
        "records",
        [
            [match(severity="High", state="not-fixed", fix_versions=[]), match(severity="High")],
            [match(severity="Low"), match(severity="Critical")],
            [match(severity="Medium"), match(severity="High")],
            [
                match(severity="Critical", state="not-fixed", fix_versions=[]),
                match(severity="Low"),
                match(severity="High"),
            ],
        ],
        ids=["unfixable-then-fixable", "low-then-critical", "medium-then-high", "three-records"],
    )
    def test_a_fixable_high_or_critical_record_fails_in_any_order(
        self, tmp_path: Path, records: list[dict]
    ) -> None:
        for ordering, result, summary in each_order(tmp_path, records):
            assert result.returncode == 1, (result.stdout, [m["vulnerability"] for m in ordering])
            assert "**FAIL**" in summary

    @pytest.mark.parametrize(
        "records",
        [
            [match(severity="Critical", state="not-fixed", fix_versions=[]), match(severity="Low")],
            [match(severity="High", state="wont-fix", fix_versions=[]), match(severity="Medium")],
        ],
        ids=["unfixable-critical-and-fixable-low", "unfixable-high-and-fixable-medium"],
    )
    def test_duplicates_without_a_fixable_high_still_pass_in_any_order(
        self, tmp_path: Path, records: list[dict]
    ) -> None:
        for ordering, result, summary in each_order(tmp_path, records):
            assert result.returncode == 0, (result.stdout, [m["vulnerability"] for m in ordering])
            assert "**PASS**" in summary

    def test_records_that_differ_are_both_reported(self, tmp_path: Path) -> None:
        _, summary = run_report(tmp_path, report(match(severity="Low"), match(severity="Critical")))

        assert "| Critical | 1 | 1 | 0 |" in summary
        assert "| Low | 1 | 1 | 0 |" in summary
        assert "| **All** | 2 | 2 | 0 |" in summary

    def test_identical_duplicates_are_one_finding_and_one_violation(self, tmp_path: Path) -> None:
        result, summary = run_report(tmp_path, report(match(), match(), match()))

        assert result.returncode == 1
        assert "| **All** | 1 | 1 | 0 |" in summary
        assert "1 fixable HIGH or above finding(s)" in summary
        assert result.stdout.count("  violation:") == 1

    def test_output_does_not_depend_on_the_order_of_matches(self, tmp_path: Path) -> None:
        records = [
            match("CVE-2026-0001", "High", package="a"),
            match("CVE-2026-0001", "Low", package="a"),
            match("CVE-2026-0002", "Low", package="b"),
            match("CVE-2026-0003", "Low", "not-fixed", [], package="c"),
        ]
        outcomes = {
            (result.returncode, result.stdout, summary)
            for _, result, summary in each_order(tmp_path, records)
        }

        assert len(outcomes) == 1, "exit code, log and summary are identical for every order"


def source_for(*repo_digests: str, kind: str = "image") -> dict:
    return {"type": kind, "target": {"userInput": "x", "repoDigests": list(repo_digests)}}


class TestTheReportMustBeForTheImageThatWasToBeScanned:
    def test_a_different_digest_is_an_error_not_a_pass(self, tmp_path: Path) -> None:
        other = "index.docker.io/acme-org/cna@sha256:" + "cd" * 32

        result, _ = run_report(tmp_path, report(source=source_for(other)))

        assert result.returncode == 2
        assert "::error title=Grype report unusable::" in result.stdout
        assert "was to be scanned" in result.stdout

    def test_the_same_digest_in_another_repository_is_an_error(self, tmp_path: Path) -> None:
        other = "index.docker.io/acme-org/other@sha256:" + "ab" * 32

        result, _ = run_report(tmp_path, report(source=source_for(other)))

        assert result.returncode == 2

    @pytest.mark.parametrize(
        "source",
        [
            None,
            {},
            {"type": "directory", "target": "/work"},
            {"type": "image"},
            {"type": "image", "target": "docker.io/acme-org/cna"},
            {"type": "image", "target": {}},
            {"type": "image", "target": {"repoDigests": []}},
            {"type": "image", "target": {"repoDigests": None}},
            {"type": "image", "target": {"repoDigests": [7, None]}},
        ],
        ids=[
            "absent",
            "empty",
            "not-an-image",
            "no-target",
            "target-is-a-string",
            "no-repo-digests",
            "empty-repo-digests",
            "null-repo-digests",
            "non-string-repo-digests",
        ],
    )
    def test_a_report_that_cannot_confirm_its_image_is_an_error(
        self, tmp_path: Path, source: object
    ) -> None:
        document = report(match(severity="Low"))
        if source is None:
            del document["source"]
        else:
            document["source"] = source

        result, _ = run_report(tmp_path, document)

        assert result.returncode == 2, result.stdout
        assert "::error title=Grype report unusable::" in result.stdout

    @pytest.mark.parametrize("host", ["index.docker.io", "docker.io", "registry-1.docker.io:443"])
    def test_any_registry_spelling_of_the_same_repository_and_digest_matches(
        self, tmp_path: Path, host: str
    ) -> None:
        recorded = f"{host}/acme-org/cna@sha256:" + "ab" * 32

        result, summary = run_report(
            tmp_path, report(match(severity="Low"), source=source_for(recorded))
        )

        assert result.returncode == 0, result.stdout
        assert "report confirms digest `sha256:" + "ab" * 32 + "`" in summary

    def test_one_matching_entry_among_several_is_enough(self, tmp_path: Path) -> None:
        recorded = [
            "index.docker.io/acme-org/cna@sha256:" + "cd" * 32,
            "index.docker.io/acme-org/cna@sha256:" + "ab" * 32,
        ]

        result, _ = run_report(tmp_path, report(source=source_for(*recorded)))

        assert result.returncode == 0, result.stdout

    @pytest.mark.parametrize(
        "image",
        [
            "docker.io/acme-org/cna:latest",
            "docker.io/acme-org/cna",
            "docker.io/acme-org/cna@sha256:" + "ab" * 31,
            "docker.io/acme-org/cna@sha256:" + "AB" * 32,
        ],
    )
    def test_the_image_to_expect_must_be_a_digest_reference(
        self, tmp_path: Path, image: str
    ) -> None:
        path = tmp_path / "grype.json"
        path.write_text(json.dumps(report()), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--report", str(path), "--name", "cli", "--image", image],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT.parent,
            env=base_env(),
        )

        assert result.returncode == 2
        assert "--image must be a digest reference" in result.stdout

    def test_a_stale_report_for_another_image_cannot_be_reused(self, tmp_path: Path) -> None:
        # The report is clean, but for a different digest: the policy must not pass on it.
        clean_other = report(source=source_for("index.docker.io/acme-org/cna@sha256:" + "ef" * 32))

        result, summary = run_report(tmp_path, clean_other)

        assert result.returncode == 2
        assert summary == ""


class TestSummary:
    def test_counts_split_fixable_from_not(self, tmp_path: Path) -> None:
        document = report(
            match("CVE-2026-0001", "High", "fixed"),
            match("CVE-2026-0002", "High", "not-fixed", [], package="zlib"),
            match("CVE-2026-0003", "Medium", "fixed", package="curl"),
            match("CVE-2026-0004", "Low", "wont-fix", [], package="tar"),
        )

        _, summary = run_report(tmp_path, document, "--fail-on", "critical")

        assert "| Critical | 0 | 0 | 0 |" in summary
        assert "| High | 2 | 1 | 1 |" in summary
        assert "| Medium | 1 | 1 | 0 |" in summary
        assert "| Low | 1 | 0 | 1 |" in summary
        assert "| **All** | 4 | 2 | 2 |" in summary

    def test_top_findings_name_package_versions_and_cve(self, tmp_path: Path) -> None:
        document = report(
            match("CVE-2026-0001", "High", fix_versions=["3.5.8-1", "3.5.9-1"], package="openssl")
        )

        _, summary = run_report(tmp_path, document)

        assert (
            "| High | CVE-2026-0001 | openssl | 3.5.7-1 | 3.5.8-1, 3.5.9-1 | deb | violation |"
            in summary
        )
        assert "`" + IMAGE + "`" in summary
        assert "Grype 0.118.0" in summary

    def test_violations_are_listed_before_other_findings(self, tmp_path: Path) -> None:
        document = report(
            match("CVE-2026-0010", "Critical", "not-fixed", [], package="aaa"),
            match("CVE-2026-0020", "Low", "fixed", package="bbb"),
            match("CVE-2026-0030", "High", "fixed", package="ccc"),
        )

        _, summary = run_report(tmp_path, document)

        order = [summary.index(cve) for cve in ("CVE-2026-0030", "CVE-2026-0020", "CVE-2026-0010")]
        assert order == sorted(order), "violation, then other fixable, then the rest"

    def test_the_table_is_capped_and_says_so(self, tmp_path: Path) -> None:
        document = report(*[match(f"CVE-2026-{n:04d}", "Low", package=f"p{n}") for n in range(20)])

        _, summary = run_report(tmp_path, document, "--top", "5")

        assert summary.count("| Low | CVE-2026-") == 5
        assert "Showing 5 of 20 findings" in summary
        assert "`grype-cli`" in summary

    def test_a_package_installed_at_several_paths_counts_once(self, tmp_path: Path) -> None:
        document = report(match(), match(), match(package="other"))

        _, summary = run_report(tmp_path, document)

        assert "| **All** | 2 | 2 | 0 |" in summary

    def test_database_build_time_is_shown_when_the_report_has_it(self, tmp_path: Path) -> None:
        document = report(match(severity="Low"))
        document["descriptor"]["db"] = {"status": {"built": "2026-10-26T01:02:03Z"}}

        _, summary = run_report(tmp_path, document)

        assert "vulnerability database built 2026-10-26T01:02:03Z" in summary

    def test_untrusted_text_cannot_break_the_table(self, tmp_path: Path) -> None:
        document = report(
            match(package="evil|pkg`x`\n| injected | row |", version="<script>1</script>")
        )

        _, summary = run_report(tmp_path, document)

        row = next(line for line in summary.splitlines() if "CVE-2026-0001" in line)
        assert row.count("|") - row.count("\\|") == 8, "still exactly seven columns"
        assert "<script>" not in summary
        assert "`x`" not in summary

    def test_untrusted_text_cannot_inject_workflow_commands(self, tmp_path: Path) -> None:
        document = report(match(package="p\n::error::forged%0A", fix_versions=["1\n::notice::x"]))

        result, _ = run_report(tmp_path, document)

        lines = result.stdout.splitlines()
        assert result.returncode == 1
        assert sum(line.startswith("::error") for line in lines) == 1
        assert not any(line.startswith("::notice") for line in lines)
        assert not any(line.startswith("::forged") for line in lines)

    def test_the_summary_is_optional(self, tmp_path: Path) -> None:
        path = tmp_path / "grype.json"
        path.write_text(json.dumps(report(match(severity="Low"))), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--report", str(path), "--name", "cli", "--image", IMAGE],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT.parent,
            env=base_env(),
        )

        assert result.returncode == 0, result.stdout + result.stderr
