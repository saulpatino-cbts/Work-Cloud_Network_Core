#!/usr/bin/env python3
"""Verify that a published image digest is signed and attested the way the appliances require.

390 runs this against every digest it scans. It is an independent re-statement of
the checks the appliances run before every deploy (their
scripts/ci/verify_image_signature.sh, called by 210 and 220), so a drift in how
200-build-images signs is caught here, in the core, before an appliance refuses a
deploy:

    1. `cosign verify` finds a keyless signature on the digest whose certificate
       carries exactly IMAGE_SIGNING_IDENTITY and SIGSTORE_OIDC_ISSUER, and the
       signed payload names the digest being checked.
    2. `cosign verify-attestation --type slsaprovenance02` finds a SLSA v0.2
       provenance attestation under the same identity.
    3. One of those statements has the digest as its subject and a
       `predicate.builder.id` that starts with EXPECTED_BUILDER_PREFIX (a workflow
       run of this repository).

cosign 3 accepts exactly one proof of signing time per verification: an RFC 3161
signed timestamp (`--use-signed-timestamps`) or Rekor's integrated timestamp (the
default). The appliances accept either, so this script tries the timestamp form
first and falls back to the default, exactly as they do.

Environment (all required; the workflow derives them from `github.*`, never from
the image or the manifest):
    IMAGE_SIGNING_IDENTITY  https://github.com/<owner>/<repo>/.github/workflows/200-build-images.yml@refs/heads/main
    SIGSTORE_OIDC_ISSUER    https://token.actions.githubusercontent.com
    EXPECTED_BUILDER_PREFIX https://github.com/<owner>/<repo>/actions/runs/

Usage:
    verify_published_image.py docker.io/<namespace>/cna@sha256:<64 hex>

cosign needs Docker CLI registry credentials (a global `docker login`) to read the
signature and attestation from the private repository.

Exit 0: signature, attestation, subject and builder all verified.
Exit 1: any check failed.
Exit 2: the script was invoked with missing or malformed input.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence

REF_PATTERN = re.compile(r"^docker\.io/[a-z0-9][a-z0-9._-]*/cna@sha256:([0-9a-f]{64})$")
# Same shape the appliances accept for IMAGE_SIGNING_IDENTITY.
IDENTITY_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\.github/workflows/"
    r"[A-Za-z0-9_.-]+\.ya?ml@refs/heads/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$"
)
PREFIX_PATTERN = re.compile(
    r"^https://[A-Za-z0-9_.:-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/$"
)
PROVENANCE_TYPE = "slsaprovenance02"
PROVENANCE_PREDICATE = "https://slsa.dev/provenance/v0.2"
TIMESTAMP_FLAG = "--use-signed-timestamps"
COSIGN_TIMEOUT_SECONDS = 300
STDERR_LIMIT = 2000

Runner = Callable[..., subprocess.CompletedProcess]


class VerifyError(Exception):
    """A verification check failed."""


class UsageError(Exception):
    """The script was invoked with missing or malformed input."""


def escape_data(message: str) -> str:
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def run_cosign(runner: Runner, args: Sequence[str]) -> tuple[subprocess.CompletedProcess, str]:
    try:
        completed = runner(
            ["cosign", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=COSIGN_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise VerifyError("cosign is not installed on this runner") from exc
    except subprocess.TimeoutExpired as exc:
        raise VerifyError(f"cosign {args[0]} timed out after {COSIGN_TIMEOUT_SECONDS}s") from exc
    return completed, (completed.stderr or "")[-STDERR_LIMIT:]


def cosign_with_either_timestamp(runner: Runner, args: Sequence[str]) -> str:
    """Run a cosign verification, accepting either signing-time proof; return stdout."""
    failures: list[str] = []
    for label, extra in (("signed timestamp", [TIMESTAMP_FLAG]), ("integrated timestamp", [])):
        completed, stderr = run_cosign(runner, [*args[:-1], *extra, args[-1]])
        if completed.returncode == 0:
            print(f"  (verified with the {label})")
            return completed.stdout or ""
        failures.append(f"--- {label}:\n{stderr.strip()}")
    raise VerifyError(
        f"cosign {args[0]} failed under both timestamp policies:\n" + "\n".join(failures)
    )


def check_signatures(stdout: str, digest: str) -> None:
    try:
        payloads = json.loads(stdout)
    except ValueError as exc:
        raise VerifyError(f"cosign verify printed output that is not JSON: {exc}") from exc
    if not isinstance(payloads, list) or not payloads:
        raise VerifyError("cosign verify reported no signature")
    for payload in payloads:
        try:
            signed = payload["critical"]["image"]["docker-manifest-digest"]
        except (KeyError, TypeError) as exc:
            raise VerifyError("a verified signature payload names no image digest") from exc
        if signed != f"sha256:{digest}":
            raise VerifyError(f"the verified signature is on {signed}, not sha256:{digest}")


def statement_of(entry: object) -> Mapping | None:
    """The in-toto statement of one verify-attestation output line.

    cosign prints either the statement itself or a DSSE envelope whose base64
    `payload` holds it; both are accepted.
    """
    if not isinstance(entry, dict):
        return None
    if "payload" in entry and "predicateType" not in entry:
        try:
            decoded = json.loads(base64.b64decode(entry["payload"], validate=True))
        except (ValueError, TypeError, binascii.Error):
            return None
        return decoded if isinstance(decoded, dict) else None
    return entry


def check_attestations(stdout: str, digest: str, builder_prefix: str) -> str:
    """Return the builder id of the first statement that satisfies every check."""
    seen: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            statement = statement_of(json.loads(line))
        except ValueError:
            continue
        if statement is None:
            continue
        subjects = [
            s.get("digest", {}).get("sha256")
            for s in statement.get("subject") or []
            if isinstance(s, dict) and isinstance(s.get("digest"), dict)
        ]
        predicate = statement.get("predicate")
        builder = predicate.get("builder") if isinstance(predicate, dict) else None
        builder_id = builder.get("id") if isinstance(builder, dict) else None
        builder_id = builder_id if isinstance(builder_id, str) else ""
        if (
            statement.get("predicateType") == PROVENANCE_PREDICATE
            and digest in subjects
            and builder_id.startswith(builder_prefix)
        ):
            return builder_id
        seen.append(
            f"predicateType={statement.get('predicateType')!r} subjects={subjects!r} "
            f"builder={builder_id!r}"
        )
    raise VerifyError(
        f"no SLSA v0.2 provenance statement has subject sha256:{digest} and a builder id "
        f"starting with {builder_prefix}. Statements seen: " + ("; ".join(seen) if seen else "none")
    )


def verify(
    ref: str,
    identity: str,
    issuer: str,
    builder_prefix: str,
    runner: Runner = subprocess.run,
) -> str:
    """Run every check; return the verified builder id. Raises VerifyError."""
    match = REF_PATTERN.fullmatch(ref)
    if not match:
        raise UsageError(f"expected docker.io/<namespace>/cna@sha256:<64 hex>, got {ref!r}")
    digest = match.group(1)
    identity_args = ["--certificate-identity", identity, "--certificate-oidc-issuer", issuer]

    print(f"verifying signature on {ref}")
    stdout = cosign_with_either_timestamp(
        runner, ["verify", *identity_args, "--output", "json", ref]
    )
    check_signatures(stdout, digest)

    print("verifying SLSA provenance attestation")
    stdout = cosign_with_either_timestamp(
        runner, ["verify-attestation", "--type", PROVENANCE_TYPE, *identity_args, ref]
    )
    return check_attestations(stdout, digest, builder_prefix)


def read_settings(env: Mapping[str, str]) -> tuple[str, str, str]:
    identity = env.get("IMAGE_SIGNING_IDENTITY", "")
    issuer = env.get("SIGSTORE_OIDC_ISSUER", "")
    prefix = env.get("EXPECTED_BUILDER_PREFIX", "")
    if not IDENTITY_PATTERN.fullmatch(identity) or "/../" in identity or "/./" in identity:
        raise UsageError(
            "IMAGE_SIGNING_IDENTITY must be a GitHub Actions workflow identity "
            "(https://github.com/<owner>/<repo>/.github/workflows/<file>.yml@refs/heads/<branch>)"
        )
    if not issuer.startswith("https://"):
        raise UsageError("SIGSTORE_OIDC_ISSUER must be an https URL")
    if not PREFIX_PATTERN.fullmatch(prefix):
        raise UsageError(
            "EXPECTED_BUILDER_PREFIX must look like https://github.com/<owner>/<repo>/actions/runs/"
        )
    return identity, issuer, prefix


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    environment = os.environ if env is None else env
    try:
        if len(args) != 1:
            raise UsageError(
                "usage: verify_published_image.py docker.io/<namespace>/cna@sha256:<64 hex>"
            )
        identity, issuer, prefix = read_settings(environment)
        builder_id = verify(args[0], identity, issuer, prefix)
    except UsageError as exc:
        print(f"::error::{escape_data(str(exc))}")
        return 2
    except VerifyError as exc:
        print(f"::error title=Image signature or provenance not verified::{escape_data(str(exc))}")
        return 1
    print(f"signature and provenance verified - identity {identity}, builder {builder_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
