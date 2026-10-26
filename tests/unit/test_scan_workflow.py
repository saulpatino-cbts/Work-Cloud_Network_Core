"""Structure tests for .github/workflows/390-scan-images.yml (TODO.md T-719).

390 cannot run before it is on the default branch, so these tests pin the wiring
that a first run would otherwise discover: the trigger name that must match
workflow 200 exactly, the least-privilege split between jobs, the pins that must
agree with 200, and the absence of anything that could make the policy check
silently green or put event data into a shell line. They read the workflow as
data; they prove the file's shape, not how GitHub behaves when it runs.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCAN_FILE = WORKFLOWS / "390-scan-images.yml"
BUILD_FILE = WORKFLOWS / "200-build-images.yml"

SHA_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def scan() -> dict:
    return load(SCAN_FILE)


@pytest.fixture(scope="module")
def build() -> dict:
    return load(BUILD_FILE)


def triggers(workflow: dict) -> dict:
    # PyYAML (YAML 1.1) reads the bare key `on` as the boolean True.
    return workflow.get("on") or workflow[True]


def all_steps(workflow: dict) -> list[dict]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def uses_of(workflow: dict, action: str) -> list[str]:
    return [s["uses"] for s in all_steps(workflow) if s.get("uses", "").startswith(action + "@")]


def test_old_scout_workflow_is_gone() -> None:
    assert SCAN_FILE.is_file()
    assert not (WORKFLOWS / "390-scout-scan.yml").exists()


def test_workflow_name(scan: dict) -> None:
    assert scan["name"] == "390 · Scan Published Images"


class TestTriggers:
    def test_workflow_run_is_wired_to_the_exact_name_of_workflow_200(
        self, scan: dict, build: dict
    ) -> None:
        run = triggers(scan)["workflow_run"]

        assert run["workflows"] == [build["name"]]
        assert run["types"] == ["completed"]

    def test_weekly_backstop_and_manual_dispatch(self, scan: dict) -> None:
        on = triggers(scan)

        assert on["schedule"] == [{"cron": "0 7 * * 1"}]
        assert "workflow_dispatch" in on
        assert set(on) == {"workflow_run", "schedule", "workflow_dispatch"}

    def test_workflow_run_only_scans_a_successful_main_run_of_this_repository(
        self, scan: dict
    ) -> None:
        condition = " ".join(str(scan["jobs"]["targets"]["if"]).split())

        assert "github.event.workflow_run.conclusion == 'success'" in condition
        assert "github.event.workflow_run.head_branch == 'main'" in condition
        assert (
            "github.event.workflow_run.head_repository.full_name == github.repository" in condition
        )
        assert condition.startswith("github.event_name != 'workflow_run' ||")

    def test_every_job_after_targets_depends_on_it(self, scan: dict) -> None:
        for name, job in scan["jobs"].items():
            if name != "targets":
                assert "targets" in job["needs"], name


class TestLeastPrivilege:
    def test_workflow_default_is_read_only(self, scan: dict) -> None:
        assert scan["permissions"] == {"contents": "read"}

    def test_only_the_scan_job_holds_the_oidc_and_code_scanning_grants(self, scan: dict) -> None:
        assert scan["jobs"]["targets"]["permissions"] == {"contents": "read"}
        assert scan["jobs"]["scan"]["permissions"] == {
            "contents": "read",
            "id-token": "write",
            "security-events": "write",
        }

    def test_every_job_has_a_timeout_and_the_workflow_never_cancels_a_scan(
        self, scan: dict
    ) -> None:
        assert scan["concurrency"]["cancel-in-progress"] is False
        for name, job in scan["jobs"].items():
            assert isinstance(job.get("timeout-minutes"), int), name

    def test_checkouts_are_main_only_and_keep_no_credentials(self, scan: dict) -> None:
        checkouts = [
            s for s in all_steps(scan) if s.get("uses", "").startswith("actions/checkout@")
        ]

        assert len(checkouts) == 2
        for step in checkouts:
            assert step["with"]["ref"] == "main"
            assert step["with"]["persist-credentials"] is False

    def test_the_run_is_refused_off_the_default_branch(self, scan: dict) -> None:
        guard = scan["jobs"]["targets"]["steps"][0]

        assert "refs/heads/main" in guard["run"]
        assert guard["env"] == {"RUN_REF": "${{ github.ref }}"}


class TestPinsAgreeWithWorkflow200:
    def test_every_action_is_pinned_to_a_full_commit_sha_with_a_version_comment(self) -> None:
        text = SCAN_FILE.read_text(encoding="utf-8")
        uses_lines = [line for line in text.splitlines() if re.match(r"\s*(- )?uses:", line)]

        assert uses_lines
        for line in uses_lines:
            reference = line.split("uses:", 1)[1].split("#", 1)[0].strip()
            assert SHA_PINNED.fullmatch(reference), line
            assert re.search(r"#\s*v\d+\.\d+\.\d+\s*$", line), f"missing version comment: {line}"

    @pytest.mark.parametrize(
        "action",
        ["actions/checkout", "docker/login-action", "sigstore/cosign-installer"],
    )
    def test_shared_actions_use_the_same_pin_as_200(
        self, scan: dict, build: dict, action: str
    ) -> None:
        in_build = set(uses_of(build, action))

        assert len(in_build) == 1, f"{action} should have one pin in 200"
        assert set(uses_of(scan, action)) == in_build

    def test_cosign_release_matches_200(self, scan: dict, build: dict) -> None:
        assert scan["env"]["COSIGN_VERSION"] == build["env"]["COSIGN_VERSION"]
        installer = next(
            s for s in all_steps(scan) if s.get("uses", "").startswith("sigstore/cosign-installer@")
        )
        assert installer["with"]["cosign-release"] == "${{ env.COSIGN_VERSION }}"

    def test_the_verified_identity_is_workflow_200_on_main(self, scan: dict) -> None:
        identity = scan["env"]["IMAGE_SIGNING_IDENTITY"]

        assert identity == (
            "https://github.com/${{ github.repository }}"
            f"/.github/workflows/{BUILD_FILE.name}@refs/heads/main"
        )
        assert scan["env"]["SIGSTORE_OIDC_ISSUER"] == "https://token.actions.githubusercontent.com"
        assert scan["env"]["EXPECTED_BUILDER_PREFIX"] == (
            "${{ github.server_url }}/${{ github.repository }}/actions/runs/"
        )


class TestDockerHubLogin:
    def test_keyless_unscoped_login_with_a_long_enough_token(self, scan: dict) -> None:
        login = next(
            s for s in all_steps(scan) if s.get("uses", "").startswith("docker/login-action@")
        )

        assert "scope" not in login["with"], "a scoped login is invisible to Grype and cosign"
        assert login["with"]["username"] == "${{ vars.DOCKERHUB_NAMESPACE }}"
        assert (
            login["env"]["DOCKERHUB_OIDC_CONNECTIONID"] == "${{ vars.DOCKERHUB_OIDC_CONNECTIONID }}"
        )
        assert login["env"]["DOCKERHUB_OIDC_EXPIREIN"] == "3600"
        assert "password" not in login["with"]


class TestScanner:
    def test_uses_grype_through_the_pinned_action_and_no_other_scanner(self, scan: dict) -> None:
        used = [s["uses"] for s in all_steps(scan) if "uses" in s]

        assert len(uses_of(scan, "anchore/scan-action")) == 2
        assert not [u for u in used if "trivy" in u.lower() or "scout" in u.lower()]

    def test_both_scans_target_the_validated_digest_by_registry_source(self, scan: dict) -> None:
        for step in (s for s in all_steps(scan) if s.get("uses", "").startswith("anchore/")):
            assert step["with"]["image"] == "registry:${{ matrix.ref }}"
            assert step["with"]["fail-build"] == "false"
            assert step["with"]["only-fixed"] == "false"

    def test_the_sarif_pass_reuses_the_database_of_the_json_pass(self, scan: dict) -> None:
        steps = {s.get("id"): s for s in all_steps(scan)}

        assert steps["grype_json"]["with"]["output-format"] == "json"
        assert steps["grype_json"]["with"]["cache-db"] == "true"
        assert steps["grype_sarif"]["with"]["output-format"] == "sarif"
        assert steps["grype_sarif"]["env"]["GRYPE_DB_AUTO_UPDATE"] == "false"
        assert "cache-db" not in steps["grype_sarif"]["with"]

    def test_grype_is_pinned_to_one_release_in_both_passes(self, scan: dict) -> None:
        # The action fetches Grype's installer by release tag inside a job that holds
        # an OIDC token and a Docker Hub credential, so the release is a deliberate pin.
        assert re.fullmatch(r"v\d+\.\d+\.\d+", scan["env"]["GRYPE_VERSION"])
        passes = [s for s in all_steps(scan) if s.get("uses", "").startswith("anchore/")]

        assert len(passes) == 2
        for step in passes:
            assert step["with"]["grype-version"] == "${{ env.GRYPE_VERSION }}"

    def test_the_policy_step_reads_the_full_report_with_the_workflow_threshold(
        self, scan: dict
    ) -> None:
        policy = next(s for s in all_steps(scan) if s.get("id") == "policy")

        assert "scripts/ci/grype_report.py" in policy["run"]
        assert '--fail-on "$SCAN_FAIL_ON"' in policy["run"]
        assert scan["env"]["SCAN_FAIL_ON"] == "high"


class TestHeaderDoesNotOverclaim:
    def test_the_signature_check_is_not_presented_as_proof_for_the_appliances(self) -> None:
        text = " ".join(SCAN_FILE.read_text(encoding="utf-8").replace("#", " ").split())

        assert "does NOT run the appliances' own verify scripts" in text
        assert "will pass" not in text
        assert "before an appliance refuses a deploy" not in text


class TestNothingCanMakeThePolicySilentlyGreen:
    def test_no_step_swallows_failure(self) -> None:
        text = SCAN_FILE.read_text(encoding="utf-8")
        code_lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]

        assert not [ln for ln in code_lines if "continue-on-error" in ln]
        assert not [ln for ln in code_lines if re.search(r"\|\|\s*true\b", ln)]

    def test_the_sarif_upload_runs_after_a_policy_failure_and_is_a_real_step(
        self, scan: dict
    ) -> None:
        upload = next(s for s in all_steps(scan) if s.get("id") == "upload")
        condition = str(upload["if"])

        assert upload["uses"].startswith("github/codeql-action/upload-sarif@")
        assert "!cancelled()" in condition or "always()" in condition
        assert "policy" not in condition, "a failed policy step must not skip the upload"
        assert "continue-on-error" not in upload
        assert upload["with"]["category"] == "grype-${{ matrix.key }}"

    def test_the_verification_and_policy_steps_run_independently_of_each_other(
        self, scan: dict
    ) -> None:
        steps = {s.get("id") or s["name"]: s for s in all_steps(scan)}
        verify = steps["Verify signature and provenance"]

        assert "scripts/ci/verify_published_image.py" in verify["run"]
        assert "continue-on-error" not in verify
        for later in ("grype_json", "grype_sarif", "policy", "upload"):
            assert "!cancelled()" in str(steps[later]["if"]), later


class TestNoEventDataInShell:
    def test_no_run_block_interpolates_any_expression(self, scan: dict) -> None:
        for step in all_steps(scan):
            if "run" in step:
                assert "${{" not in step["run"], step.get("name")

    def test_event_values_reach_scripts_only_through_env(self, scan: dict) -> None:
        resolve = next(s for s in all_steps(scan) if s.get("id") == "resolve")

        assert resolve["env"]["RUN_HEAD_SHA"] == "${{ github.event.workflow_run.head_sha }}"
        assert resolve["env"]["EVENT_NAME"] == "${{ github.event_name }}"
        assert resolve["run"].strip() == "python3 scripts/ci/resolve_scan_targets.py"

    def test_every_script_the_workflow_runs_exists(self, scan: dict) -> None:
        for step in all_steps(scan):
            for script in re.findall(r"scripts/ci/[\w.]+", step.get("run", "")):
                assert (REPO_ROOT / script).is_file(), script
