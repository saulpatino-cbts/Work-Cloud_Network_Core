#!/usr/bin/env python3
"""Resolve the image digests that workflow 390 scans.

390 scans exactly what the appliances deploy: the `digests{}` of
`.deployment-catalog/latest-build.json` on main, which 200-build-images'
`publish-build-manifest` job commits after every main publish. This script reads
that manifest, validates every reference, and hands the scan job a JSON matrix.

Configuration comes from the environment, never from interpolated workflow
expressions (the workflow passes `github.event.*` values through `env:`):

    DOCKERHUB_NAMESPACE  Docker Hub organisation; every digest must be under it.
    EVENT_NAME           workflow_run | schedule | workflow_dispatch.
    RUN_HEAD_SHA         workflow_run only: commit the finished 200 run built.
    GITHUB_OUTPUT        optional: receives `matrix`, `has_targets`, `commit`.
    GITHUB_STEP_SUMMARY  optional: receives a short note on what will be scanned.

Until the first main publish the committed manifest is a placeholder (all-zero
`commit`, no `digests{}`). That is "nothing published yet": a green skip with a
warning on the weekly `schedule`, a failure for `workflow_run` and
`workflow_dispatch`, where someone expects a scan to have happened.

For `workflow_run` the manifest `commit` is compared with the run's head SHA. A
mismatch means a newer publish superseded the run (or the manifest push lost a
race); the manifest is still what the appliances deploy, so it is scanned, with
a visible warning.

Exit 0: targets resolved, or an allowed "nothing published yet" skip.
Exit 1: nothing to scan where a scan was expected, or the manifest is invalid.
Exit 2: the script itself was invoked with missing or malformed configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

# The contract with the appliances (CLAUDE.md, contract item 2): these five keys,
# in this order. A key added to or removed from the manifest must be a deliberate
# change here, so a new image can never be deployed without being scanned.
IMAGE_KEYS = ("cli", "api", "worker", "web", "migrator")
DEFAULT_MANIFEST = ".deployment-catalog/latest-build.json"
EVENTS = ("workflow_run", "schedule", "workflow_dispatch")

NAMESPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
BUILT_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PLACEHOLDER_COMMIT = "0" * 40
# Longest value echoed back in an error message: manifest content is data.
ECHO_LIMIT = 120


class ManifestError(Exception):
    """The manifest is unreadable or violates the contract with the appliances."""


class ConfigError(Exception):
    """The script was invoked with missing or malformed configuration."""


def escape_command(message: str) -> str:
    """Escape a message for a GitHub workflow command (`::error::...`)."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotate(level: str, message: str) -> None:
    print(f"::{level}::{escape_command(message)}")


def echo(value: object) -> str:
    """A bounded, single-line rendering of untrusted manifest content."""
    text = repr(value)
    return text if len(text) <= ECHO_LIMIT else text[: ECHO_LIMIT - 3] + "..."


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"cannot read the build manifest {path}: {exc}") from exc
    except ValueError as exc:
        raise ManifestError(f"the build manifest {path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ManifestError(f"the build manifest {path} is not a JSON object")
    commit = manifest.get("commit")
    if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
        raise ManifestError(
            f"the build manifest has no 40-hex `commit` (got {echo(commit)}); "
            "200-build-images writes one on every publish"
        )
    return manifest


def nothing_published_reason(manifest: Mapping) -> str | None:
    """Why the manifest holds nothing to scan, or None when it lists digests."""
    if manifest["commit"] == PLACEHOLDER_COMMIT:
        return (
            "the committed build manifest is still the placeholder (all-zero commit): "
            "no main publish of 200-build-images has landed yet"
        )
    digests = manifest.get("digests")
    if not digests:
        return (
            f"the build manifest for commit {manifest['commit'][:7]} records no digests{{}} "
            "(it was published before 200-build-images recorded digests)"
        )
    return None


def build_targets(digests: object, namespace: str) -> list[dict[str, str]]:
    """Validate `digests{}` against the contract and return the scan targets."""
    if not isinstance(digests, dict):
        raise ManifestError(f"`digests` is not an object (got {echo(digests)})")
    problems: list[str] = []
    unknown = sorted(str(key) for key in digests if key not in IMAGE_KEYS)
    if unknown:
        problems.append(
            f"unexpected image key(s) {unknown}: add them to IMAGE_KEYS in "
            "scripts/ci/resolve_scan_targets.py so they are scanned"
        )
    pattern = re.compile(rf"^docker\.io/{re.escape(namespace)}/cna@sha256:[0-9a-f]{{64}}$")
    targets: list[dict[str, str]] = []
    for key in IMAGE_KEYS:
        if key not in digests:
            problems.append(f"digests.{key} is missing")
            continue
        ref = digests[key]
        if not isinstance(ref, str) or not pattern.fullmatch(ref):
            problems.append(
                f"digests.{key} {echo(ref)} is not docker.io/{namespace}/cna@sha256:<64 hex>"
            )
            continue
        targets.append({"key": key, "ref": ref})
    if problems:
        raise ManifestError("invalid digests{} in the build manifest: " + "; ".join(problems))
    return targets


def read_config(env: Mapping[str, str]) -> tuple[str, str, str]:
    namespace = env.get("DOCKERHUB_NAMESPACE", "")
    if not NAMESPACE_PATTERN.fullmatch(namespace):
        raise ConfigError(
            "DOCKERHUB_NAMESPACE must be set to the Docker Hub organisation "
            f"(lowercase letters, digits, '.', '_' or '-'); got {echo(namespace)}"
        )
    event = env.get("EVENT_NAME", "")
    if event not in EVENTS:
        raise ConfigError(f"EVENT_NAME must be one of {', '.join(EVENTS)}; got {echo(event)}")
    head_sha = env.get("RUN_HEAD_SHA", "")
    if event == "workflow_run" and not COMMIT_PATTERN.fullmatch(head_sha):
        raise ConfigError(
            f"RUN_HEAD_SHA must be the 40-hex head commit of the 200 run; got {echo(head_sha)}"
        )
    return namespace, event, head_sha


def append_file(env: Mapping[str, str], variable: str, text: str) -> None:
    target = env.get(variable)
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(text)


def write_outputs(env: Mapping[str, str], targets: list[dict[str, str]], commit: str) -> None:
    matrix = json.dumps({"include": targets}, separators=(",", ":"))
    append_file(
        env,
        "GITHUB_OUTPUT",
        f"matrix={matrix}\nhas_targets={'true' if targets else 'false'}\ncommit={commit}\n",
    )
    print(f"matrix={matrix}")


def write_summary(env: Mapping[str, str], manifest: Mapping, targets: list[dict[str, str]]) -> None:
    built_at = manifest.get("built_at")
    built_at = (
        built_at
        if isinstance(built_at, str) and BUILT_AT_PATTERN.fullmatch(built_at)
        else "unknown"
    )
    lines = [
        "### Scan targets",
        "",
        f"Manifest commit `{manifest['commit'][:7]}`, built {built_at}. "
        "These are the digests the appliances deploy.",
        "",
        "| Image | Digest |",
        "| --- | --- |",
    ]
    lines += [f"| {t['key']} | `{t['ref'].rsplit('@', 1)[1]}` |" for t in targets]
    append_file(env, "GITHUB_STEP_SUMMARY", "\n".join(lines) + "\n\n")


def run(manifest_path: Path, env: Mapping[str, str]) -> int:
    try:
        namespace, event, head_sha = read_config(env)
    except ConfigError as exc:
        annotate("error", str(exc))
        return 2

    try:
        manifest = load_manifest(manifest_path)
        reason = nothing_published_reason(manifest)
        if reason is not None:
            if event == "schedule":
                annotate("warning", f"Nothing to scan: {reason}. Skipping this scheduled scan.")
                write_outputs(env, [], manifest["commit"])
                return 0
            annotate(
                "error",
                f"Nothing to scan: {reason}. A {event} run expects published digests; "
                "check that 200-build-images' publish-build-manifest job committed the manifest.",
            )
            return 1
        targets = build_targets(manifest["digests"], namespace)
    except ManifestError as exc:
        annotate("error", str(exc))
        return 1

    if event == "workflow_run" and manifest["commit"] != head_sha:
        annotate(
            "warning",
            f"The finished 200 run built {head_sha[:7]} but the manifest on main records "
            f"{manifest['commit'][:7]}: a newer publish superseded it, or the manifest push "
            "lost a race. Scanning the digests in the manifest, which is what the appliances deploy.",
        )
    write_outputs(env, targets, manifest["commit"])
    write_summary(env, manifest, targets)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(DEFAULT_MANIFEST),
        help=f"path to the build manifest (default: {DEFAULT_MANIFEST})",
    )
    args = parser.parse_args(argv)
    return run(args.manifest, os.environ)


if __name__ == "__main__":
    sys.exit(main())
