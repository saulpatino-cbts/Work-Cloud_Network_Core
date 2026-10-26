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
             version, fix version and CVE id.

Findings are the DISTINCT match records of the report: two matches that are
identical in vulnerability, package, version, type, severity and fix are one
finding (a package installed at several paths), but two that differ in severity or
fix state are two findings. Nothing is merged across a difference, so a fixable
HIGH or CRITICAL record can never be hidden by a duplicate that is less severe or
not fixable, whatever order Grype listed them in.

An unreadable, empty or structurally unexpected report is an error (exit 2),
never a pass: a scan that produced nothing must not look like a clean image. So is
a report that does not say it scanned the image named by --image: Grype records
the registry digest of its source in `source.target.repoDigests` (stereoscope
builds it as `<registry>/<repository>@<digest of the descriptor the reference
resolved to>`, which for a by-digest reference is the digest asked for, an image
index's own digest included), and that digest and repository must match. The
registry host is not compared: stereoscope spells Docker Hub `index.docker.io`.

Usage:
    grype_report.py --report PATH --name NAME --image DIGEST_REF [--fail-on SEVERITY] [--top N]

DIGEST_REF is the immutable reference that was scanned,
`<registry>/<repository>@sha256:<64 hex>`.

Exit 0: the report is valid and holds no fixable finding at or above --fail-on.
Exit 1: it holds at least one (policy violated).
Exit 2: the report could not be read or understood, or the arguments are invalid.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
DIGEST_REF_PATTERN = re.compile(r"^(?P<repository>[^@\s]+)@(?P<digest>sha256:[0-9a-f]{64})$")


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

    def identity(self) -> tuple:
        """The whole match record. Two findings are the same only if nothing differs."""
        return (
            self.vuln_id,
            self.package,
            self.version,
            self.package_type,
            self.severity,
            self.fix_state,
            self.fix_versions,
        )


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
    findings = {}
    for index, match in enumerate(document["matches"]):
        finding = parse_finding(index, match)
        findings[finding.identity()] = finding
    return document, sorted(findings.values(), key=sort_key)


def violations_of(findings: list[Finding], fail_on: str) -> list[Finding]:
    """Fixable findings at or above the threshold, most severe first."""
    threshold = SEVERITIES.index(fail_on.capitalize())
    hits = [f for f in findings if f.fixable and f.rank <= threshold]
    return sorted(hits, key=sort_key)


def sort_key(finding: Finding) -> tuple:
    """A total order over findings, so output never depends on Grype's match order."""
    return (finding.rank, *finding.identity())


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


def check_scanned_image(document: dict, image: str) -> str:
    """Confirm the report is for `image`; return the digest. Raises ReportError."""
    expected = DIGEST_REF_PATTERN.fullmatch(image)
    if not expected:
        raise ReportError(
            "--image must be a digest reference <registry>/<repository>@sha256:<64 hex>; "
            f"got {cell(image, IMAGE_LIMIT)!r}"
        )
    # Drop the registry host: stereoscope spells docker.io as index.docker.io.
    repository = expected["repository"].split("/", 1)[-1]
    source = document.get("source")
    if not isinstance(source, dict) or source.get("type") != "image":
        kind = source.get("type") if isinstance(source, dict) else None
        raise ReportError(f"the report's source is not an image scan (source.type is {kind!r})")
    target = source.get("target")
    recorded = target.get("repoDigests") if isinstance(target, dict) else None
    if not isinstance(recorded, list) or not recorded:
        raise ReportError(
            "the report records no source.target.repoDigests, so it cannot confirm which "
            f"image was scanned (expected {expected['digest']})"
        )
    for entry in recorded:
        if not isinstance(entry, str):
            continue
        entry_repository, _, entry_digest = entry.partition("@")
        if entry_digest == expected["digest"] and entry_repository.split("/", 1)[-1] == repository:
            return expected["digest"]
    raise ReportError(
        f"the report was produced for {cell(', '.join(map(str, recorded)), IMAGE_LIMIT)} "
        f"but {repository}@{expected['digest']} was to be scanned"
    )


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
    digest: str,
) -> str:
    descriptor = document.get("descriptor")
    grype_version = descriptor.get("version") if isinstance(descriptor, dict) else ""
    built = database_built(document)
    provenance = " | ".join(
        part
        for part in (
            f"Grype {cell(grype_version)}" if grype_version else "",
            f"vulnerability database built {cell(built)}" if built else "",
            f"report confirms digest `{cell(digest, IMAGE_LIMIT)}`",
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
        lines.append(
            "0 matches: confirm the vulnerability database was current "
            "(see its build time above) and that the image was catalogued."
        )
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
        digest = check_scanned_image(document, args.image)
    except ReportError as exc:
        print(f"::error title={escape_property('Grype report unusable')}::{escape_data(str(exc))}")
        return 2

    violations = violations_of(findings, args.fail_on)
    summary = render_summary(
        args.name, args.image, document, findings, violations, args.fail_on, args.top, digest
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
