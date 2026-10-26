"""Tests for scripts/ci/resolve_scan_targets.py (TODO.md T-719).

The script decides what workflow 390 scans, so its failure modes matter: it must
never scan a reference that is not exactly `docker.io/<namespace>/cna@sha256:<64>`,
must treat "nothing published yet" as a skip only on the weekly schedule, and must
surface a superseded `workflow_run`. Each case runs the real entry point as a
subprocess from an unrelated working directory, with a minimal environment, the
way the repository's other CI-script tests do.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "resolve_scan_targets.py"
REAL_MANIFEST = REPO_ROOT / ".deployment-catalog" / "latest-build.json"

NAMESPACE = "acme-org"
IMAGE_KEYS = ("cli", "api", "worker", "web", "migrator")
COMMIT = "1234567" + "a" * 33
OTHER_COMMIT = "7654321" + "b" * 33
PLACEHOLDER_COMMIT = "0" * 40


def digest_ref(seed: str, namespace: str = NAMESPACE) -> str:
    return f"docker.io/{namespace}/cna@sha256:{seed * 32}"


def published_manifest(commit: str = COMMIT) -> dict:
    return {
        "sha_tag": f"sha-{commit[:7]}",
        "commit": commit,
        "built_at": "2026-10-26T07:00:00Z",
        "run_id": "123",
        "images": {key: f"docker.io/{NAMESPACE}/cna:{key}-sha-{commit[:7]}" for key in IMAGE_KEYS},
        "digests": {key: digest_ref(f"{i:02x}"[-2:]) for i, key in enumerate(IMAGE_KEYS, start=10)},
    }


def placeholder_manifest() -> dict:
    manifest = published_manifest(PLACEHOLDER_COMMIT)
    del manifest["digests"]
    return manifest


def run_script(
    tmp_path: Path,
    manifest: dict | str | None,
    event: str,
    *,
    namespace: str | None = NAMESPACE,
    head_sha: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess, dict[str, str], str]:
    """Run the script; return the process, parsed GITHUB_OUTPUT and the step summary."""
    manifest_path = tmp_path / "latest-build.json"
    if manifest is not None:
        manifest_path.write_text(
            manifest if isinstance(manifest, str) else json.dumps(manifest), encoding="utf-8"
        )
    github_output = tmp_path / "github_output"
    step_summary = tmp_path / "step_summary"
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    env.update(
        {
            "EVENT_NAME": event,
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(step_summary),
        }
    )
    if namespace is not None:
        env["DOCKERHUB_NAMESPACE"] = namespace
    if head_sha is not None:
        env["RUN_HEAD_SHA"] = head_sha
    env.update(extra_env or {})
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(manifest_path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT.parent,
        env=env,
    )
    outputs: dict[str, str] = {}
    if github_output.exists():
        for line in github_output.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            outputs[name] = value
    summary = step_summary.read_text(encoding="utf-8") if step_summary.exists() else ""
    return result, outputs, summary


class TestResolvesPublishedManifest:
    @pytest.mark.parametrize("event", ["workflow_dispatch", "schedule"])
    def test_emits_one_matrix_entry_per_image(self, tmp_path: Path, event: str) -> None:
        manifest = published_manifest()
        result, outputs, summary = run_script(tmp_path, manifest, event)

        assert result.returncode == 0, result.stdout + result.stderr
        assert outputs["has_targets"] == "true"
        assert outputs["commit"] == COMMIT
        matrix = json.loads(outputs["matrix"])
        assert [t["key"] for t in matrix["include"]] == list(IMAGE_KEYS)
        assert {t["key"]: t["ref"] for t in matrix["include"]} == manifest["digests"]
        assert "::warning" not in result.stdout
        assert "| cli |" in summary

    def test_workflow_run_for_the_published_commit_scans_without_a_warning(
        self, tmp_path: Path
    ) -> None:
        result, outputs, _ = run_script(
            tmp_path, published_manifest(), "workflow_run", head_sha=COMMIT
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert outputs["has_targets"] == "true"
        assert "::warning" not in result.stdout

    def test_workflow_run_for_a_superseded_commit_warns_but_still_scans(
        self, tmp_path: Path
    ) -> None:
        result, outputs, _ = run_script(
            tmp_path, published_manifest(COMMIT), "workflow_run", head_sha=OTHER_COMMIT
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert outputs["has_targets"] == "true"
        assert json.loads(outputs["matrix"])["include"], "the manifest digests are still scanned"
        warning = next(
            line for line in result.stdout.splitlines() if line.startswith("::warning::")
        )
        assert OTHER_COMMIT[:7] in warning and COMMIT[:7] in warning
        assert "superseded" in warning

    def test_namespace_is_matched_literally_not_as_a_regex(self, tmp_path: Path) -> None:
        # '.' is a legal namespace character; it must not match any other character.
        manifest = published_manifest()
        manifest["digests"] = {key: digest_ref("ab", "a.b") for key in IMAGE_KEYS}

        accepted, _, _ = run_script(tmp_path, manifest, "schedule", namespace="a.b")
        assert accepted.returncode == 0, accepted.stdout

        rejected, _, _ = run_script(tmp_path, manifest, "schedule", namespace="axb")
        assert rejected.returncode == 1


class TestNothingPublishedYet:
    def test_schedule_skips_with_a_warning(self, tmp_path: Path) -> None:
        result, outputs, _ = run_script(tmp_path, placeholder_manifest(), "schedule")

        assert result.returncode == 0, result.stdout + result.stderr
        assert outputs["has_targets"] == "false"
        assert json.loads(outputs["matrix"]) == {"include": []}
        assert "::warning::" in result.stdout and "placeholder" in result.stdout
        assert "::error" not in result.stdout

    @pytest.mark.parametrize("event", ["workflow_run", "workflow_dispatch"])
    def test_other_events_fail_loudly(self, tmp_path: Path, event: str) -> None:
        result, outputs, _ = run_script(
            tmp_path, placeholder_manifest(), event, head_sha=PLACEHOLDER_COMMIT
        )

        assert result.returncode == 1
        assert "has_targets" not in outputs
        error = next(line for line in result.stdout.splitlines() if line.startswith("::error::"))
        assert "Nothing to scan" in error and "placeholder" in error and event in error

    def test_a_real_commit_without_digests_is_also_nothing_to_scan(self, tmp_path: Path) -> None:
        manifest = published_manifest()
        del manifest["digests"]

        skipped, outputs, _ = run_script(tmp_path, manifest, "schedule")
        assert skipped.returncode == 0
        assert outputs["has_targets"] == "false"
        assert "records no digests" in skipped.stdout

        failed, _, _ = run_script(tmp_path, manifest, "workflow_dispatch")
        assert failed.returncode == 1

    def test_an_empty_digests_object_counts_as_nothing_published(self, tmp_path: Path) -> None:
        manifest = published_manifest()
        manifest["digests"] = {}

        result, outputs, _ = run_script(tmp_path, manifest, "schedule")

        assert result.returncode == 0
        assert outputs["has_targets"] == "false"


class TestRejectsInvalidManifests:
    @pytest.mark.parametrize(
        "bad_ref",
        [
            "docker.io/acme-org/cna:latest",  # a tag, not a digest
            "docker.io/acme-org/cna@sha256:" + "ab" * 31,  # 62 hex characters
            "docker.io/acme-org/cna@sha256:" + "AB" * 32,  # upper-case hex
            "docker.io/acme-org/cna@sha256:" + "ab" * 32 + "\n",  # trailing newline
            "docker.io/acme-org/cna@sha256:" + "ab" * 32 + "x",  # trailing text
            "docker.io/other-org/cna@sha256:" + "ab" * 32,  # another namespace
            "ghcr.io/acme-org/cna@sha256:" + "ab" * 32,  # another registry
            "docker.io/acme-org/other@sha256:" + "ab" * 32,  # another repository
            "docker.io/acme-org/cna@sha512:" + "ab" * 32,  # another algorithm
            "-v /:/host docker.io/acme-org/cna@sha256:" + "ab" * 32,  # option injection
            "",
            None,
            42,
        ],
    )
    def test_a_malformed_digest_reference_fails(self, tmp_path: Path, bad_ref: object) -> None:
        manifest = published_manifest()
        manifest["digests"]["web"] = bad_ref

        result, outputs, _ = run_script(tmp_path, manifest, "workflow_dispatch")

        assert result.returncode == 1
        assert "matrix" not in outputs
        assert "digests.web" in result.stdout

    def test_a_missing_image_key_fails(self, tmp_path: Path) -> None:
        manifest = published_manifest()
        del manifest["digests"]["migrator"]

        result, _, _ = run_script(tmp_path, manifest, "schedule")

        assert result.returncode == 1
        assert "digests.migrator is missing" in result.stdout

    def test_an_unexpected_image_key_fails_so_it_cannot_ship_unscanned(
        self, tmp_path: Path
    ) -> None:
        manifest = published_manifest()
        manifest["digests"]["extra"] = digest_ref("cd")

        result, _, _ = run_script(tmp_path, manifest, "schedule")

        assert result.returncode == 1
        assert "extra" in result.stdout and "IMAGE_KEYS" in result.stdout

    def test_digests_that_are_not_an_object_fail(self, tmp_path: Path) -> None:
        manifest = published_manifest()
        manifest["digests"] = [digest_ref("ab")]

        result, _, _ = run_script(tmp_path, manifest, "schedule")

        assert result.returncode == 1
        assert "not an object" in result.stdout

    @pytest.mark.parametrize(
        "text",
        ["{not json", "[]", '"a string"', "{}", json.dumps({"commit": "abc"})],
    )
    def test_an_unusable_manifest_fails_even_on_schedule(self, tmp_path: Path, text: str) -> None:
        result, outputs, _ = run_script(tmp_path, text, "schedule")

        assert result.returncode == 1
        assert "has_targets" not in outputs
        assert "::error::" in result.stdout

    def test_a_missing_manifest_fails(self, tmp_path: Path) -> None:
        result, _, _ = run_script(tmp_path, None, "schedule")

        assert result.returncode == 1
        assert "cannot read the build manifest" in result.stdout

    def test_untrusted_manifest_text_cannot_inject_workflow_commands(self, tmp_path: Path) -> None:
        manifest = published_manifest()
        manifest["digests"]["cli"] = "x\n::set-output name=pwned::1"

        result, _, _ = run_script(tmp_path, manifest, "schedule")

        assert result.returncode == 1
        assert not any(line.startswith("::set-output") for line in result.stdout.splitlines()), (
            "a newline in manifest content must not start a second workflow command"
        )


class TestRejectsBadConfiguration:
    @pytest.mark.parametrize("namespace", [None, "", "Upper", "-lead", "has space", "a/b", "a;b"])
    def test_bad_namespace(self, tmp_path: Path, namespace: str | None) -> None:
        result, outputs, _ = run_script(
            tmp_path, published_manifest(), "workflow_dispatch", namespace=namespace
        )

        assert result.returncode == 2
        assert "DOCKERHUB_NAMESPACE" in result.stdout
        assert "matrix" not in outputs

    @pytest.mark.parametrize("event", ["", "push", "pull_request", "WORKFLOW_RUN"])
    def test_unknown_event(self, tmp_path: Path, event: str) -> None:
        result, _, _ = run_script(tmp_path, published_manifest(), event)

        assert result.returncode == 2
        assert "EVENT_NAME" in result.stdout

    @pytest.mark.parametrize("head_sha", [None, "", "abc123", "Z" * 40, COMMIT.upper()])
    def test_workflow_run_requires_a_head_sha(self, tmp_path: Path, head_sha: str | None) -> None:
        result, _, _ = run_script(tmp_path, published_manifest(), "workflow_run", head_sha=head_sha)

        assert result.returncode == 2
        assert "RUN_HEAD_SHA" in result.stdout


class TestCommittedManifest:
    """The manifest in this repository must always be something 390 can classify."""

    def test_the_committed_manifest_is_accepted_in_its_current_state(self, tmp_path: Path) -> None:
        manifest = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
        match = re.fullmatch(r"docker\.io/([^/]+)/cna:.+", manifest["images"]["cli"])
        assert match, "images.cli no longer has the docker.io/<namespace>/cna:<tag> form"

        result, outputs, _ = run_script(
            tmp_path, REAL_MANIFEST.read_text(encoding="utf-8"), "schedule", namespace=match[1]
        )

        # Either still the placeholder (a warned skip) or published (valid digests).
        # Neither may be an error: that would mean 200's manifest writer and 390's
        # reader have drifted apart.
        assert result.returncode == 0, result.stdout + result.stderr
        assert outputs["has_targets"] in {"true", "false"}
        if outputs["has_targets"] == "false":
            assert manifest["commit"] == PLACEHOLDER_COMMIT or not manifest.get("digests")
