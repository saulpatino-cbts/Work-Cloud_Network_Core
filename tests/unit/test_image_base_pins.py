"""Static guard for the shared Python runtime security floor."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_DOCKERFILES = (
    ROOT / "Dockerfile",
    ROOT / "apps" / "cna-api" / "Dockerfile",
)
PYTHON_BASE = re.compile(
    r"^FROM (python:(\d+)\.(\d+)\.(\d+)-slim@sha256:[0-9a-f]{64})(?: AS \S+)?$"
)
MINIMUM_PATCH = (3, 14, 10)


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
