"""Tests for scripts/ci/verify_published_image.py (TODO.md T-719).

390 uses this script to prove, for every digest it scans, that the appliances'
signature and provenance checks will pass. cosign itself is not available here, so
the verification logic is exercised against a fake runner that returns the output
shapes cosign prints; that proves the decisions (which digests, identities and
builders are accepted), not cosign's own behaviour. The first real run of 390 is
what proves the two together.
"""

import base64
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "verify_published_image.py"

_spec = importlib.util.spec_from_file_location("verify_published_image", SCRIPT)
assert _spec and _spec.loader
verify_published_image = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = verify_published_image
_spec.loader.exec_module(verify_published_image)

DIGEST = "ab" * 32
REF = f"docker.io/acme-org/cna@sha256:{DIGEST}"
IDENTITY = "https://github.com/acme/core/.github/workflows/200-build-images.yml@refs/heads/main"
ISSUER = "https://token.actions.githubusercontent.com"
PREFIX = "https://github.com/acme/core/actions/runs/"
BUILDER = PREFIX + "42/attempts/1"


def signature_output(digest: str = DIGEST) -> str:
    return json.dumps([{"critical": {"image": {"docker-manifest-digest": f"sha256:{digest}"}}}])


def statement(
    digest: str = DIGEST,
    builder: str = BUILDER,
    predicate_type: str = "https://slsa.dev/provenance/v0.2",
) -> dict:
    return {
        "_type": "https://in-toto.io/Statement/v0.1",
        "predicateType": predicate_type,
        "subject": [{"name": "docker.io/acme-org/cna", "digest": {"sha256": digest}}],
        "predicate": {"builder": {"id": builder}},
    }


def envelope(stmt: dict) -> dict:
    payload = base64.b64encode(json.dumps(stmt).encode()).decode()
    return {"payloadType": "application/vnd.in-toto+json", "payload": payload, "signatures": []}


def lines(*entries: dict) -> str:
    return "\n".join(json.dumps(e) for e in entries) + "\n"


class FakeCosign:
    """Stands in for subprocess.run; replies by sub-command, optionally per timestamp policy."""

    def __init__(self, *, verify_out=None, attest_out=None, fail_timestamp=False, fail_all=False):
        self.verify_out = signature_output() if verify_out is None else verify_out
        self.attest_out = lines(statement()) if attest_out is None else attest_out
        self.fail_timestamp = fail_timestamp
        self.fail_all = fail_all
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        assert kwargs["capture_output"] is True and kwargs["check"] is False
        stamped = "--use-signed-timestamps" in cmd
        if self.fail_all or (self.fail_timestamp and stamped):
            return subprocess.CompletedProcess(cmd, 1, "", f"boom stamped={stamped}")
        out = self.verify_out if cmd[1] == "verify" else self.attest_out
        return subprocess.CompletedProcess(cmd, 0, out, "")


def verify(fake: FakeCosign) -> str:
    return verify_published_image.verify(REF, IDENTITY, ISSUER, PREFIX, runner=fake)


class TestVerify:
    def test_accepts_a_signed_and_attested_digest(self) -> None:
        fake = FakeCosign()

        assert verify(fake) == BUILDER

        verify_call, attest_call = fake.calls
        assert verify_call[:2] == ["cosign", "verify"]
        assert attest_call[:2] == ["cosign", "verify-attestation"]
        assert ["--type", "slsaprovenance02"] == attest_call[2:4]
        for call in fake.calls:
            assert call[call.index("--certificate-identity") + 1] == IDENTITY
            assert call[call.index("--certificate-oidc-issuer") + 1] == ISSUER
            assert call[-1] == REF, "the reference is the last argument"
        assert "--use-signed-timestamps" in verify_call
        assert verify_call[verify_call.index("--output") + 1] == "json"

    def test_falls_back_to_the_integrated_timestamp(self) -> None:
        fake = FakeCosign(fail_timestamp=True)

        assert verify(fake) == BUILDER

        assert [("--use-signed-timestamps" in call) for call in fake.calls] == [
            True,
            False,
            True,
            False,
        ]

    def test_fails_when_both_timestamp_policies_fail(self) -> None:
        with pytest.raises(verify_published_image.VerifyError) as error:
            verify(FakeCosign(fail_all=True))

        assert "both timestamp policies" in str(error.value)
        assert "stamped=True" in str(error.value) and "stamped=False" in str(error.value)

    def test_a_missing_cosign_binary_is_a_verification_failure(self) -> None:
        def missing(cmd, **kwargs):
            raise FileNotFoundError("cosign")

        with pytest.raises(verify_published_image.VerifyError, match="cosign is not installed"):
            verify_published_image.verify(REF, IDENTITY, ISSUER, PREFIX, runner=missing)

    @pytest.mark.parametrize(
        "verify_out",
        [
            "[]",
            "null",
            "not json",
            json.dumps([{"critical": {}}]),
            signature_output("cd" * 32),
            json.dumps(
                json.loads(signature_output())
                + json.loads(signature_output("cd" * 32))  # one good, one on another digest
            ),
        ],
        ids=[
            "empty-list",
            "null",
            "not-json",
            "no-digest-in-payload",
            "other-digest",
            "one-good-one-other-digest",
        ],
    )
    def test_rejects_a_signature_that_is_missing_or_on_another_digest(
        self, verify_out: str
    ) -> None:
        with pytest.raises(verify_published_image.VerifyError):
            verify(FakeCosign(verify_out=verify_out))

    @pytest.mark.parametrize(
        ("attest_out", "reason"),
        [
            ("", "none"),
            ("not json\n", "none"),
            (lines(statement(predicate_type="https://slsa.dev/provenance/v1")), "provenance/v1"),
            (lines(statement(digest="cd" * 32)), "subjects"),
            (lines(statement(builder="https://github.com/acme/other/actions/runs/42")), "other"),
            (lines(statement(builder="https://github.com/acme/core-evil/actions/runs/42")), "evil"),
            (lines(statement(builder="")), "builder=''"),
            (lines({"predicateType": "https://slsa.dev/provenance/v0.2"}), "subjects=[]"),
        ],
        ids=[
            "empty",
            "not-json",
            "slsa-v1",
            "other-subject-digest",
            "other-repository",
            "prefix-sibling-repository",
            "no-builder-id",
            "no-subject",
        ],
    )
    def test_rejects_provenance_that_does_not_match(self, attest_out: str, reason: str) -> None:
        with pytest.raises(verify_published_image.VerifyError) as error:
            verify(FakeCosign(attest_out=attest_out))

        assert "no SLSA v0.2 provenance statement" in str(error.value)
        assert reason in str(error.value)

    def test_accepts_when_any_one_statement_matches(self) -> None:
        bad = statement(builder="https://github.com/acme/other/actions/runs/1")
        fake = FakeCosign(attest_out=lines(bad, statement()))

        assert verify(fake) == BUILDER

    def test_accepts_a_dsse_envelope_as_well_as_a_bare_statement(self) -> None:
        assert verify(FakeCosign(attest_out=lines(envelope(statement())))) == BUILDER

    def test_rejects_an_envelope_with_an_undecodable_payload(self) -> None:
        broken = {"payloadType": "application/vnd.in-toto+json", "payload": "!!!", "signatures": []}

        with pytest.raises(verify_published_image.VerifyError):
            verify(FakeCosign(attest_out=lines(broken)))

    @pytest.mark.parametrize(
        "ref",
        [
            "docker.io/acme-org/cna:latest",
            f"docker.io/acme-org/cna@sha256:{DIGEST}\n",
            f"ghcr.io/acme-org/cna@sha256:{DIGEST}",
            f"docker.io/acme-org/cna@sha256:{DIGEST[:-1]}",
            f"--insecure-ignore-tlog docker.io/acme-org/cna@sha256:{DIGEST}",
        ],
    )
    def test_rejects_a_reference_that_is_not_a_docker_hub_digest(self, ref: str) -> None:
        fake = FakeCosign()

        with pytest.raises(verify_published_image.UsageError):
            verify_published_image.verify(ref, IDENTITY, ISSUER, PREFIX, runner=fake)

        assert fake.calls == [], "cosign must not run for a malformed reference"


def run_main(env_overrides: dict[str, str | None], *args: str) -> subprocess.CompletedProcess:
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    env.update(
        {
            "IMAGE_SIGNING_IDENTITY": IDENTITY,
            "SIGSTORE_OIDC_ISSUER": ISSUER,
            "EXPECTED_BUILDER_PREFIX": PREFIX,
        }
    )
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT.parent,
        env=env,
    )


class TestEntryPoint:
    @pytest.mark.parametrize(
        "override",
        [
            {"IMAGE_SIGNING_IDENTITY": None},
            {"IMAGE_SIGNING_IDENTITY": "not-an-identity"},
            {"IMAGE_SIGNING_IDENTITY": IDENTITY.replace("/workflows/", "/../workflows/")},
            {"IMAGE_SIGNING_IDENTITY": IDENTITY.replace("@refs/heads/main", "")},
            {"SIGSTORE_OIDC_ISSUER": None},
            {"SIGSTORE_OIDC_ISSUER": "http://insecure.example"},
            {"EXPECTED_BUILDER_PREFIX": None},
            {"EXPECTED_BUILDER_PREFIX": "https://github.com/acme/core"},
            {"EXPECTED_BUILDER_PREFIX": "https://github.com/acme/core/actions/runs"},
        ],
    )
    def test_refuses_to_run_without_a_well_formed_trust_policy(
        self, override: dict[str, str | None]
    ) -> None:
        result = run_main(override, REF)

        assert result.returncode == 2, result.stdout + result.stderr
        assert "::error::" in result.stdout

    @pytest.mark.parametrize("args", [[], [REF, REF], ["docker.io/acme-org/cna:latest"]])
    def test_refuses_the_wrong_arguments(self, args: list[str]) -> None:
        result = run_main({}, *args)

        assert result.returncode == 2, result.stdout + result.stderr
        assert "::error::" in result.stdout
