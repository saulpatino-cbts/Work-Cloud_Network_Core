"""Static guards for the shared Python and web runtime security floors.

Every Python ``FROM`` line in both Python Dockerfiles must be the same digest-pinned
``python:<major>.<minor>.<patch>-slim-trixie`` base, at or above the patched floor.
The tag must name the Debian release (trixie): a future Debian release under the
floating ``-slim`` tag cannot then move an image to another distribution unnoticed.
The shared-digest rule is why a Dependabot base bump must land in one pull request
across ``/`` and ``/apps/cna-api`` (the ``python-base`` group in
``.github/dependabot.yml``): split per directory, each half fails this test.
All web stages must likewise share a digest-pinned Node base at or above the patched floor.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_DOCKERFILES = (
    ROOT / "Dockerfile",
    ROOT / "apps" / "cna-api" / "Dockerfile",
)
PYTHON_BASE = re.compile(
    r"^FROM (python:(\d+)\.(\d+)\.(\d+)-slim-trixie@sha256:[0-9a-f]{64})(?: AS \S+)?$"
)
NODE_BASE = re.compile(r"^FROM (node:(\d+)\.(\d+)\.(\d+)-alpine@sha256:[0-9a-f]{64}) AS (\S+)$")
# Python 3.15.2 on Debian 13.7, 2026-11-12: 3.14.10 carried CVE-2026-119170, fixed only
# in 3.14.11, for which no image exists (TODO.md T-726, T-727).
MINIMUM_PATCH = (3, 15, 2)


def test_python_stages_share_a_digest_pinned_patched_runtime() -> None:
    references = set()
    for path in PYTHON_DOCKERFILES:
        stages = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("FROM python:")
        ]
        assert stages, path
        for stage in stages:
            match = PYTHON_BASE.fullmatch(stage)
            assert match, (path, stage)
            version = tuple(int(part) for part in match.group(2, 3, 4))
            assert version >= MINIMUM_PATCH, (path, version)
            references.add(match[1])
    assert len(references) == 1, references


def test_a_base_without_the_debian_release_in_its_tag_is_rejected() -> None:
    digest = "0" * 64
    assert PYTHON_BASE.fullmatch(f"FROM python:3.15.2-slim-trixie@sha256:{digest} AS builder")
    assert not PYTHON_BASE.fullmatch(f"FROM python:3.15.2-slim@sha256:{digest} AS builder")
    assert not PYTHON_BASE.fullmatch(f"FROM python:3.15.2-slim-bookworm@sha256:{digest}")
    assert not PYTHON_BASE.fullmatch("FROM python:3.15.2-slim-trixie AS builder")


def test_web_stages_share_a_digest_pinned_patched_node() -> None:
    path = ROOT / "apps" / "cna-web" / "Dockerfile"
    stages = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("FROM ")
    ]
    references = set()
    names = set()
    for stage in stages:
        match = NODE_BASE.fullmatch(stage)
        assert match, (path, stage)
        version = tuple(int(part) for part in match.group(2, 3, 4))
        assert version >= (26, 13, 1), (path, version)  # Fixes seven HIGH Node CVEs in 26.13.0.
        references.add(match[1])
        names.add(match[5])
    assert names == {"deps", "builder", "migrator", "runner"}
    assert len(references) == 1, references
