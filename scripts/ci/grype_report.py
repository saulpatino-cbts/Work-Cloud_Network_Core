#!/usr/bin/env python3
"""Turn one Grype JSON report into a job summary and the policy verdict for 390.

390 scans every published digest with Anchore Grype and keeps the JSON report of
*all* matches (not just fixable ones). This script is the policy decision and the
human-readable report, both computed from that one file so they cannot disagree:

    policy   a FIXABLE finding at or above --fail-on (default: high) fails the job;
             everything else is reported and gates nothing. "Fixable" is Grype's own
             `vulnerability.fix.state == "fixed"`, the predicate behind its
             `--only-fixed`, so the verdict equals `grype --only-fixed --fail-on high`.
    report   a Markdown summary appended to $GITHUB_STEP_SUMMARY: severity counts
             (fixable and not), then the top findings with package, installed
             version, fix version and CVE id. Counts are distinct
             vulnerability x package-version pairs, so a package installed at
             several paths counts once.

An unreadable, empty or structurally unexpected report is an error (exit 2),
never a pass: a scan that produced nothing must not look like a clean image.

Usage:
    grype_report.py --report PATH --name NAME --image REF [--fail-on SEVERITY] [--top N]

Exit 0: the report is valid and holds no fixable finding at or above --fail-on.
Exit 1: it holds at least one (policy violated).
Exit 2: the report could not be read or understood, or the arguments are invalid.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Most to least severe. Position is the rank; lower is more severe.
SEVERITIES = ("Critical", "High", "Medium", "Low", "Negligible", "Unknown")
FIXED_STATE = "fixed"
DEFAULT_FAIL_ON = "high"
DEFAULT_TOP = 15
# Violations echoed to the log (the summary table is capped separately by --top).
LOG_VIOLATION_LIMIT = 50
# Violations named in the red annotation on the run page.
ANNOTATION_VIOLATION_LIMIT = 5
CELL_LIMIT = 80
DESCRIBE_LIMIT = 200
# The scanned reference is shown whole: the digest is what was scanned.
IMAGE_LIMIT = 200


class ReportError(Exception):
    """The Grype report is unreadable or does not have the expected structure."""


@dataclass(frozen=True)
class Finding:
    severity: str
    vuln_id: str
    package: str
    version: str
    package_type: str
    fix_state: str
    fix_versions: tuple[str, ...]

    @property
    def fixable(self) -> bool:
        return self.fix_state == FIXED_STATE

    @property
    def rank(self) -> int:
        return SEVERITIES.index(self.severity)

    def identity(self) -> tuple[str, str, str, str]:
        return (self.vuln_id, self.package, self.version, self.package_type)


def escape_data(message: str) -> str:
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    return escape_data(value).replace(":", "%3A").replace(",", "%2C")


def cell(value: object, limit: int = CELL_LIMIT) -> str:
    """Render untrusted report text safely inside a Markdown table cell."""
    text = " ".join(str(value).split())
    text = text.replace("`", "'").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def normalise_severity(raw: object) -> str:
    text = str(raw or "").strip().capitalize()
    return text if text in SEVERITIES else "Unknown"


def parse_finding(index: int, match: object) -> Finding:
    if not isinstance(match, dict):
        raise ReportError(f"matches[{index}] is not an object")
    vulnerability = match.get("vulnerability")
    artifact = match.get("artifact")
    if not isinstance(vulnerability, dict) or not isinstance(artifact, dict):
        raise ReportError(f"matches[{index}] lacks a vulnerability or artifact object")
    vuln_id = vulnerability.get("id")
    package = artifact.get("name")
    if not isinstance(vuln_id, str) or not vuln_id or not isinstance(package, str) or not package:
        raise ReportError(f"matches[{index}] lacks a vulnerability id or package name")
    fix = vulnerability.get("fix")
    fix = fix if isinstance(fix, dict) else {}
    versions = fix.get("versions")
    return Finding(
        severity=normalise_severity(vulnerability.get("severity")),
        vuln_id=vuln_id,
        package=package,
        version=str(artifact.get("version") or ""),
        package_type=str(artifact.get("type") or ""),
        fix_state=str(fix.get("state") or ""),
        fix_versions=tuple(str(v) for v in versions) if isinstance(versions, list) else (),
    )


def load_report(path: Path) -> tuple[dict, list[Finding]]:
    """Read the report and return its document and the distinct findings."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"cannot read the Grype report {path}: {exc}") from exc
    if not raw.strip():
        raise ReportError(f"the Grype report {path} is empty")
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise ReportError(f"the Grype report {path} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("matches"), list):
        raise ReportError(f"the Grype report {path} has no `matches` list")
    seen: dict[tuple[str, str, str, str], Finding] = {}
    for index, match in enumerate(document["matches"]):
        finding = parse_finding(index, match)
        seen.setdefault(finding.identity(), finding)
    return document, list(seen.values())


def violations_of(findings: list[Finding], fail_on: str) -> list[Finding]:
    """Fixable findings at or above the threshold, most severe first."""
    threshold = SEVERITIES.index(fail_on.capitalize())
    hits = [f for f in findings if f.fixable and f.rank <= threshold]
    return sorted(hits, key=sort_key)


def sort_key(finding: Finding) -> tuple[int, str, str]:
    return (finding.rank, finding.vuln_id, finding.package)


def describe(finding: Finding) -> str:
    """One bounded line naming a finding. Package text is untrusted: collapsing every
    line break keeps it from starting a line of its own, and so from becoming a
    workflow command in the job log."""
    fix = ", ".join(finding.fix_versions) or "-"
    text = " ".join(
        f"{finding.severity.upper()} {finding.vuln_id} {finding.package} "
        f"{finding.version or '?'} -> {fix}".split()
    )
    return text if len(text) <= DESCRIBE_LIMIT else text[: DESCRIBE_LIMIT - 3] + "..."


def database_built(document: dict) -> str:
    descriptor = document.get("descriptor")
    database = descriptor.get("db") if isinstance(descriptor, dict) else None
    if isinstance(database, dict):
        for holder in (database, database.get("status")):
            if isinstance(holder, dict) and isinstance(holder.get("built"), str):
                return holder["built"]
    return ""


def render_summary(
    name: str,
    image: str,
    document: dict,
    findings: list[Finding],
    violations: list[Finding],
    fail_on: str,
    top: int,
) -> str:
    descriptor = document.get("descriptor")
    grype_version = descriptor.get("version") if isinstance(descriptor, dict) else ""
    built = database_built(document)
    provenance = " | ".join(
        part
        for part in (
            f"Grype {cell(grype_version)}" if grype_version else "",
            f"vulnerability database built {cell(built)}" if built else "",
        )
        if part
    )
    gate = f"fixable {fail_on.upper()} or above"
    verdict = (
        f"**FAIL** - {len(violations)} {gate} finding(s)"
        if violations
        else f"**PASS** - no {gate} findings"
    )
    lines = [f"### Vulnerability scan: {cell(name)}", "", f"`{cell(image, IMAGE_LIMIT)}`"]
    if provenance:
        lines += ["", provenance]
    lines += [
        "",
        f"Policy: {verdict}. Everything else below is reported and gates nothing.",
        "",
        "| Severity | Total | Fixable | No fix |",
        "| --- | ---: | ---: | ---: |",
    ]
    for severity in SEVERITIES:
        at_level = [f for f in findings if f.severity == severity]
        fixable = sum(1 for f in at_level if f.fixable)
        lines.append(f"| {severity} | {len(at_level)} | {fixable} | {len(at_level) - fixable} |")
    fixable_total = sum(1 for f in findings if f.fixable)
    lines.append(
        f"| **All** | {len(findings)} | {fixable_total} | {len(findings) - fixable_total} |"
    )
    violating = {f.identity() for f in violations}
    # Policy violations first, then other fixable findings, then the rest.
    ordered = sorted(
        findings,
        key=lambda f: (f.identity() not in violating, not f.fixable, *sort_key(f)),
    )
    lines += ["", "#### Top findings", ""]
    if not ordered:
        lines.append("No findings.")
    else:
        lines += [
            "| Severity | CVE | Package | Installed | Fixed in | Type | Policy |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for f in ordered[:top]:
            lines.append(
                f"| {f.severity} | {cell(f.vuln_id)} | {cell(f.package)} | {cell(f.version)} "
                f"| {cell(', '.join(f.fix_versions) or '-')} | {cell(f.package_type)} "
                f"| {'violation' if f.identity() in violating else '-'} |"
            )
        if len(ordered) > top:
            lines += [
                "",
                f"Showing {top} of {len(ordered)} findings. The full list is in the "
                "code scanning alerts for this image (category `grype-" + cell(name) + "`).",
            ]
    return "\n".join(lines) + "\n\n"


def run(args: argparse.Namespace, env: dict[str, str]) -> int:
    try:
        document, findings = load_report(args.report)
    except ReportError as exc:
        print(f"::error title={escape_property('Grype report unusable')}::{escape_data(str(exc))}")
        return 2

    violations = violations_of(findings, args.fail_on)
    summary = render_summary(
        args.name, args.image, document, findings, violations, args.fail_on, args.top
    )
    summary_path = env.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)

    fixable_total = sum(1 for f in findings if f.fixable)
    print(
        f"{args.name}: {len(findings)} distinct findings, {fixable_total} fixable, "
        f"{len(violations)} fixable at {args.fail_on.upper()} or above"
    )
    if not findings:
        print(
            f"::warning::{escape_data(args.name)}: the Grype report holds zero findings. "
            "That is possible for a fully patched image but unusual; confirm the vulnerability "
            "database loaded and the image was catalogued."
        )
    for finding in violations[:LOG_VIOLATION_LIMIT]:
        print(f"  violation: {describe(finding)}")
    if len(violations) > LOG_VIOLATION_LIMIT:
        print(f"  ... and {len(violations) - LOG_VIOLATION_LIMIT} more")

    if violations:
        named = "; ".join(describe(f) for f in violations[:ANNOTATION_VIOLATION_LIMIT])
        more = len(violations) - ANNOTATION_VIOLATION_LIMIT
        suffix = f"; and {more} more" if more > 0 else ""
        title = escape_property(f"Fixable {args.fail_on.upper()}+ vulnerabilities in {args.name}")
        print(
            f"::error title={title}::"
            + escape_data(
                f"{len(violations)} fixable finding(s) at {args.fail_on.upper()} or above in "
                f"{args.image}: {named}{suffix}"
            )
        )
        return 1
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", type=Path, required=True, help="Grype JSON report")
    parser.add_argument("--name", required=True, help="short image name, e.g. cli")
    parser.add_argument("--image", required=True, help="image reference that was scanned")
    parser.add_argument(
        "--fail-on",
        default=DEFAULT_FAIL_ON,
        type=str.lower,
        choices=[s.lower() for s in SEVERITIES if s != "Unknown"],
        help=f"lowest severity that fails the job when fixable (default: {DEFAULT_FAIL_ON})",
    )
    parser.add_argument(
        "--top", type=int, default=DEFAULT_TOP, help="findings listed in the summary table"
    )
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv), dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
