"""Static wiring and offline guard checks, not Scout authentication proof."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / ".github" / "workflows" / "390-scout-review.yml"
SCOUT_SHA = "e7e2a72bf1485d10a58f30696b6c513b261ce4fa"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(FILE.read_text(encoding="utf-8"))


def steps(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def test_manual_main_only_and_read_only(workflow: dict) -> None:
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"targets", "scout"}
    assert "github.ref == 'refs/heads/main'" in workflow["jobs"]["scout"]["if"]
    assert workflow["jobs"]["scout"]["needs"] == "targets"
    assert workflow["jobs"]["scout"]["strategy"]["fail-fast"] is False
    assert workflow["jobs"]["scout"]["strategy"]["max-parallel"] == 2
    for job in workflow["jobs"].values():
        assert job.get("permissions", workflow["permissions"]) == {"contents": "read"}
        assert job["timeout-minutes"] <= 30


def test_targets_are_resolved_without_inputs_or_credential_fallback(workflow: dict) -> None:
    target_steps = steps(workflow, "targets")
    assert [s["name"] for s in target_steps[:2]] == [
        "Require main",
        "Require approved Scout credentials",
    ]
    checkout = target_steps[2]
    assert checkout["with"]["ref"] == "main"
    assert checkout["with"]["persist-credentials"] is False
    assert ".deployment-catalog" in checkout["with"]["sparse-checkout"]
    resolve = target_steps[3]
    assert resolve["run"] == "python3 scripts/ci/resolve_scan_targets.py"
    assert resolve["env"] == {
        "DOCKERHUB_NAMESPACE": "${{ vars.DOCKERHUB_NAMESPACE }}",
        "EVENT_NAME": "workflow_dispatch",
    }
    assert workflow["jobs"]["targets"]["outputs"]["matrix"] == "${{ steps.resolve.outputs.matrix }}"
    auth = target_steps[1]
    assert auth["env"] == {
        "SCOUT_USER": "${{ secrets.SCOUT_DOCKERHUB_USER }}",
        "SCOUT_PAT": "${{ secrets.SCOUT_DOCKERHUB_PAT }}",
    }
    assert "No OIDC fallback" in auth["run"]
    assert "exit 1" in auth["run"]


def test_official_scout_scans_exact_digest_without_writes(workflow: dict) -> None:
    scout = steps(workflow, "scout")[0]
    assert scout["uses"] == f"docker/scout-action@{SCOUT_SHA}"
    assert scout["with"] == {
        "command": "cves",
        "image": "registry://${{ matrix.ref }}",
        "platform": "linux/amd64",
        "dockerhub-user": "${{ secrets.SCOUT_DOCKERHUB_USER }}",
        "dockerhub-password": "${{ secrets.SCOUT_DOCKERHUB_PAT }}",
        "github-token": "${{ github.token }}",
        "write-comment": False,
        "summary": True,
        "exit-code": False,
    }
    assert workflow["jobs"]["scout"]["strategy"]["matrix"] == (
        "${{ fromJSON(needs.targets.outputs.matrix) }}"
    )
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            assert "continue-on-error" not in step
            if "uses" in step:
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"])
                assert step["uses"].split("@")[0] in {"actions/checkout", "docker/scout-action"}
            if "run" in step:
                assert "${{" not in step["run"]
                for forbidden in ("docker push", "docker build", "docker login", "gh ", "curl "):
                    assert forbidden not in step["run"]
    text = FILE.read_text(encoding="utf-8")
    for forbidden in ("id-token:", "security-events:", "registry-write-", "only-fixed:", "sarif-file:"):
        assert forbidden not in text
    assert "zero-vulnerability verdict" in text


def bash_path() -> str:
    if os.name == "nt":
        git_bash = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        )
        if git_bash.is_file():
            return str(git_bash)
    bash = shutil.which("bash")
    if bash:
        return bash
    pytest.skip("Bash unavailable; offline shell guards not executed")


def run_guard(script: str, values: dict[str, str]) -> subprocess.CompletedProcess:
    # Do not inherit credentials from the host into even an offline test.
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP") if key in os.environ}
    env.update(values)
    return subprocess.run(
        [bash_path(), "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/heads/topic", "refs/tags/main", ""])
def test_main_guard_executes_offline(workflow: dict, ref: str) -> None:
    result = run_guard(steps(workflow, "targets")[0]["run"], {"RUN_REF": ref})
    assert result.returncode == (0 if ref == "refs/heads/main" else 1)


@pytest.mark.parametrize("user,pat", [("", ""), ("fixture-user", ""), ("", "fixture-not-a-token")])
def test_missing_secret_fails_explicitly_offline(workflow: dict, user: str, pat: str) -> None:
    result = run_guard(
        steps(workflow, "targets")[1]["run"], {"SCOUT_USER": user, "SCOUT_PAT": pat}
    )
    assert result.returncode == 1
    assert "::error::Configure approved" in result.stdout
    assert "fixture-" not in result.stdout


def test_present_secret_guard_is_not_an_auth_probe(workflow: dict) -> None:
    result = run_guard(
        steps(workflow, "targets")[1]["run"],
        {"SCOUT_USER": "fixture-user", "SCOUT_PAT": "fixture-not-a-token"},
    )
    assert result.returncode == 0
    assert not result.stdout


def test_all_inline_shell_blocks_parse(workflow: dict) -> None:
    scripts = [
        step["run"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "run" in step and step["name"] != "Resolve published digests"
    ]
    assert len(scripts) == 3
    for script in scripts:
        result = subprocess.run(
            [bash_path(), "-n", "-c", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
