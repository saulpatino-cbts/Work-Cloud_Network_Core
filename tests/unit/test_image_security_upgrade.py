"""Static guard: every shipped image stage applies its distribution's security updates (TODO.md T-727).

Ported from saulpatinojr/HCW-NetworkEyes_App ``tests/unit/test_ci_hygiene.py`` (its T-741 checks).

Why: the base images are pinned by digest, and a distribution security upload reaches the mirrors
(Debian trixie-security, Alpine main) days or weeks before the official image is rebuilt with it.
On 2026-11-12 ``390-scan-images`` failed every image on fixes no base digest carried (zlib1g
``+deb13u1`` in the Python images, zlib ``1.4-r0`` in the web images), so the shipped final stages
run ``apt-get upgrade`` / ``apk upgrade``. This reverses T-702's "no upgrade" rule.

What is checked:

* each shipped stage runs the upgrade, not neutralised (no ``||`` / ``;`` fallback, no simulate or
  dry-run flag), in a RUN that names the per-run ``PUBLISH_CACHE_BUST`` build argument; every
  apt-get in a shipped stage runs with download retries off, and every update with ``--error-on=any``;
* the stages checked are the stages built: the last stage of the root and API Dockerfiles (what a
  build without ``target`` produces) is ``final``, and every image build in ``200`` and ``300``
  builds a listed stage, with ``200`` building exactly the listed set;
* every cached image build in ``200`` and ``300`` passes a ``PUBLISH_CACHE_BUST`` that differs per
  run, so the Actions BuildKit cache never replays an older upgrade result.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW_200 = WORKFLOWS / "200-build-images.yml"
WORKFLOW_300 = WORKFLOWS / "300-test-codebase.yml"

# The stages 200-build-images.yml pushes, by Dockerfile. The list is exact: a renamed or new shipped
# stage must be added here with the upgrade in place. The intermediate stages (builder, drawio-fetch,
# deps) never reach Docker Hub and are not listed.
SHIPPED_STAGES = {
    "Dockerfile": {"final"},
    "apps/cna-api/Dockerfile": {"final"},
    "apps/cna-web/Dockerfile": {"migrator", "runner"},
}
# `upgrade` anywhere in one apt-get command, whatever options precede it (`-o X`, `-oX`, `--option=X`).
APT_UPGRADE = re.compile(r"(?:^|\s)apt-get\s(?:[^&|;]*\s)?upgrade(?:\s|$)")
APK_UPGRADE = re.compile(r"(?:^|\s)apk upgrade(?:\s|$)")
# A fallback or a no-op flag would keep the RUN green while the upgrade does nothing.
NEUTRALISED = re.compile(
    r"\|\||;|(?:^|\s)(?:-s|--simulate|--dry-run|--just-print|--recon|--no-act)(?:\s|$)"
)
# `apt` as well as `apt-get`: either one downloads, so either one must run with retries off.
APT_WITHOUT_RETRIES_OFF = re.compile(r"\bapt(?:-get)?\s+(?!-o Acquire::Retries=0\s)\S+")
# Every apt option given on the command line (`-o X`, `-oX`, `--option X`, `--option=X`). In the upgrade RUN the
# only one allowed is `Acquire::Retries=0`: anything else (`APT::Get::Simulate=true`, `Debug::NoLocking`, ...)
# could turn the upgrade into a no-op that still exits 0.
APT_OPTION = re.compile(r"(?:^|\s)(?:-o|--option)(?:\s+|=)?(?P<value>\S+)")
ALLOWED_APT_OPTION = "Acquire::Retries=0"
CACHE_BUST_ARG = "PUBLISH_CACHE_BUST"
CACHE_BUST_VALUE = "PUBLISH_CACHE_BUST=${{ github.run_id }}-${{ github.run_attempt }}"
MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}")


def instructions(text: str) -> list[tuple[int, str, str]]:
    """(line number, KEYWORD, arguments) per Dockerfile instruction; continuations joined, comments dropped."""
    result: list[tuple[int, str, str]] = []
    pending, start = "", 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if not pending:
            start = number
        if pending and line.startswith("#"):
            continue  # a comment line inside a continued instruction
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        full = (pending + line).strip()
        pending = ""
        keyword, _, arguments = full.partition(" ")
        result.append((start, keyword.upper(), arguments.strip()))
    return result


def stage_names(text: str) -> list[str]:
    """The name of every stage in order; an unnamed stage is ``""``."""
    names = []
    for _, keyword, arguments in instructions(text):
        if keyword == "FROM":
            parts = arguments.split()
            names.append(parts[2] if len(parts) >= 3 and parts[1].upper() == "AS" else "")
    return names


def last_stage_problems(text: str, expected: set[str]) -> list[str]:
    """A build without ``target`` builds the LAST stage; it must be a shipped stage the guard checks."""
    names = stage_names(text)
    if not names:
        return ["no FROM instruction"]
    if names[-1] not in expected:
        return [
            f"the last stage is {names[-1]!r}, not one of {sorted(expected)}: an untargeted build ships it"
        ]
    return []


def upgrade_problems(text: str, expected: set[str]) -> list[str]:
    """Every reason the shipped stages in ``expected`` fail the T-727 rule; empty when they pass."""
    stages: dict[str, list[tuple[int, str]]] = {}
    declared: dict[str, int] = {}  # stage -> line of its `ARG PUBLISH_CACHE_BUST`
    current = ""
    for number, keyword, arguments in instructions(text):
        if keyword == "FROM":
            parts = arguments.split()
            current = parts[2] if len(parts) >= 3 and parts[1].upper() == "AS" else ""
            stages.setdefault(current, [])
        elif keyword == "RUN" and current:
            stages[current].append((number, arguments))
        elif keyword == "ARG" and current and arguments.split("=")[0].strip() == CACHE_BUST_ARG:
            declared[current] = number
    problems: list[str] = []
    missing = expected - set(stages)
    if missing:
        problems.append(f"shipped stage(s) not found as a named FROM: {sorted(missing)}")
    for stage in sorted(expected & set(stages)):
        # Every apt-get anywhere in a shipped stage: retries off (apt below 3.0.4 has CVE-2026-109518,
        # whose exploit needs a download retry), and every update refuses to pass an unfetchable index.
        for number, arguments in stages[stage]:
            if APT_WITHOUT_RETRIES_OFF.search(arguments):
                problems.append(f"line {number}: an apt-get in stage {stage} runs with retries on")
            for update in re.finditer(
                r"\bapt(?:-get)?(?: -o \S+)* update(?P<rest>[^&|;]*)", arguments
            ):
                if "--error-on=any" not in update.group("rest"):
                    problems.append(
                        f"line {number}: an apt-get update in stage {stage} lacks --error-on=any"
                    )
        upgrades = [
            (n, a) for n, a in stages[stage] if APT_UPGRADE.search(a) or APK_UPGRADE.search(a)
        ]
        if not upgrades:
            problems.append(f"stage {stage} runs no apt-get upgrade / apk upgrade")
        for number, arguments in upgrades:
            if NEUTRALISED.search(arguments):
                problems.append(
                    f"line {number}: the upgrade RUN has a fallback (`||`, `;`) or a simulate/dry-run flag"
                )
            for option in APT_OPTION.finditer(arguments):
                if option.group("value") != ALLOWED_APT_OPTION:
                    problems.append(
                        f"line {number}: the upgrade RUN sets apt option {option.group('value')!r}; "
                        f"only {ALLOWED_APT_OPTION} is allowed"
                    )
            # An ARG declared but not named in the command would not change the cache key.
            if not (stage in declared and declared[stage] < number):
                problems.append(
                    f"line {number}: no `ARG {CACHE_BUST_ARG}` earlier in stage {stage}"
                )
            if "${" + CACHE_BUST_ARG + "}" not in arguments:
                problems.append(f"line {number}: the upgrade RUN does not name {CACHE_BUST_ARG}")
            if APK_UPGRADE.search(arguments):
                if not re.search(r"apk upgrade --no-cache(?:\s|$)", arguments):
                    problems.append(
                        f"line {number}: apk upgrade leaves its index cache in the layer"
                    )
                continue
            if "apt-get -o Acquire::Retries=0 update --error-on=any" not in arguments:
                problems.append(
                    f"line {number}: no apt-get update before the upgrade in the same RUN"
                )
            elif arguments.index(" update") > arguments.index(" upgrade"):
                problems.append(f"line {number}: apt-get upgrade runs before apt-get update")
            if "rm -rf /var/lib/apt/lists/*" not in arguments:
                problems.append(f"line {number}: the apt lists are left in the layer")
    return problems


def image_builds(workflow: dict) -> list[tuple[str, str, dict]]:
    """(job id, step name, resolved `with`) for every docker/build-push-action step, one per matrix entry."""
    builds = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        include = ((job.get("strategy") or {}).get("matrix") or {}).get("include") or [{}]
        for step in job.get("steps") or []:
            if not str(step.get("uses", "")).lower().startswith("docker/build-push-action@"):
                continue
            for entry in include:
                resolved = {
                    key: MATRIX_REF.sub(
                        lambda m, e=entry: str(e.get(m.group(1), m.group(0))), str(v)
                    )
                    for key, v in (step.get("with") or {}).items()
                }
                builds.append((job_id, str(step.get("name", "")), resolved))
    return builds


def built_stage(file: str, target: str) -> str:
    """The stage a build of ``file`` produces: ``target``, or the last stage when no target is given."""
    if target:
        return target
    names = stage_names((ROOT / file).read_text(encoding="utf-8"))
    return names[-1] if names else ""


def build_problems(workflow: dict, name: str, *, exact: bool) -> list[str]:
    """Builds of an unlisted stage or Dockerfile, and (``exact``) shipped stages the workflow never builds."""
    problems: list[str] = []
    built: set[tuple[str, str]] = set()
    for job_id, step_name, with_ in image_builds(workflow):
        file = with_.get("file", "Dockerfile").removeprefix("./")
        if file not in SHIPPED_STAGES:
            problems.append(
                f"{name}: {job_id} / {step_name} builds an unlisted Dockerfile {file!r}"
            )
            continue
        stage = built_stage(file, with_.get("target", "").strip())
        built.add((file, stage))
        if stage not in SHIPPED_STAGES[file]:
            problems.append(
                f"{name}: {job_id} / {step_name} builds stage {stage!r} of {file}, "
                f"not one of {sorted(SHIPPED_STAGES[file])}"
            )
    if exact:
        expected = {(f, s) for f, stages in SHIPPED_STAGES.items() for s in stages}
        if built != expected:
            problems.append(f"{name}: builds {sorted(built)}, expected exactly {sorted(expected)}")
    return problems


def shell_builds(workflow: dict) -> list[tuple[str, str]]:
    """(job id, command) for every `docker build` / `docker buildx build` in a `run:` script."""
    builds = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            script = re.sub(r"\\\n\s*", " ", str(step.get("run", "")))  # join continued lines
            for line in script.splitlines():
                if re.search(r"\bdocker\s+(?:buildx\s+)?build\b", line):
                    builds.append((job_id, line.strip()))
    return builds


def shell_build_problems(workflow: dict, name: str) -> list[str]:
    """A shell build that does not pass the per-run cache bust, or builds a stage the guard does not check."""
    problems: list[str] = []
    for job_id, command in shell_builds(workflow):
        if CACHE_BUST_VALUE not in command:
            problems.append(
                f"{name}: {job_id} runs `{command}` without --build-arg {CACHE_BUST_VALUE}"
            )
        file_match = re.search(r"(?:-f|--file)[\s=]+(\S+)", command)
        file = (file_match.group(1) if file_match else "Dockerfile").strip("\"'").removeprefix("./")
        target_match = re.search(r"--target[\s=]+(\S+)", command)
        target = target_match.group(1).strip("\"'") if target_match else ""
        if file not in SHIPPED_STAGES:
            problems.append(f"{name}: {job_id} builds an unlisted Dockerfile {file!r}")
        elif built_stage(file, target) not in SHIPPED_STAGES[file]:
            problems.append(
                f"{name}: {job_id} builds stage {built_stage(file, target)!r} of {file}"
            )
    return problems


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.mark.parametrize("relative", sorted(SHIPPED_STAGES))
def test_every_shipped_stage_applies_the_distribution_security_updates(relative: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")
    assert upgrade_problems(text, SHIPPED_STAGES[relative]) == []


@pytest.mark.parametrize("relative", ["Dockerfile", "apps/cna-api/Dockerfile"])
def test_the_untargeted_build_is_the_checked_final_stage(relative: str) -> None:
    # 200 and 300 build these two without a `target`, which builds the LAST stage. A stage appended after
    # `final` would ship without the guard ever looking at it.
    text = (ROOT / relative).read_text(encoding="utf-8")
    assert last_stage_problems(text, SHIPPED_STAGES[relative]) == []


def test_200_builds_exactly_the_checked_stages() -> None:
    assert build_problems(load(WORKFLOW_200), "200", exact=True) == []


def test_300_builds_only_checked_stages() -> None:
    assert build_problems(load(WORKFLOW_300), "300", exact=False) == []


def test_300s_shell_builds_pass_the_cache_bust_and_build_checked_stages() -> None:
    # The CLI "Docker Build Smoke Test" builds the root Dockerfile with a plain `docker build`.
    workflow = load(WORKFLOW_300)
    assert len(shell_builds(workflow)) == 1, shell_builds(workflow)
    assert shell_build_problems(workflow, "300") == []


@pytest.mark.parametrize(("path", "count"), [(WORKFLOW_200, 4), (WORKFLOW_300, 3)])
def test_every_cached_image_build_passes_a_per_run_cache_bust(path: Path, count: int) -> None:
    builds = image_builds(load(path))
    # 200: the CLI and API matrix legs, the web runner and the migrator. 300: the api, web and migrator legs.
    assert len(builds) == count, [(j, s) for j, s, _ in builds]
    for job_id, step_name, with_ in builds:
        assert CACHE_BUST_VALUE in with_.get("build-args", "").split("\n"), (
            f"{path.name}: {job_id} / {step_name} passes no per-run {CACHE_BUST_ARG}"
        )


# --- the checkers themselves reject what they must ---

_DIGEST = "0" * 64
_GOOD_DEBIAN = f"""\
FROM python:3.15.2-slim-trixie@sha256:{_DIGEST} AS builder
RUN apt-get update && apt-get install -y curl
FROM python:3.15.2-slim-trixie@sha256:{_DIGEST} AS final
ARG PUBLISH_CACHE_BUST=
RUN printf 'upgrade run: %s\\n' "${{PUBLISH_CACHE_BUST}}" \\
 && apt-get -o Acquire::Retries=0 update --error-on=any \\
 && apt-get -o Acquire::Retries=0 upgrade -y --no-install-recommends \\
 && apt-get -o Acquire::Retries=0 install -y --no-install-recommends graphviz \\
 && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 1001 cna
"""

_GOOD_ALPINE = f"""\
FROM node:26-alpine@sha256:{_DIGEST} AS runner
ARG PUBLISH_CACHE_BUST=
RUN printf 'upgrade run: %s\\n' "${{PUBLISH_CACHE_BUST}}" \\
 && apk upgrade --no-cache
"""

_UPGRADE = " \\\n && apt-get -o Acquire::Retries=0 upgrade -y --no-install-recommends"


def test_the_checker_accepts_the_reference_shapes() -> None:
    # The builder stage's plain apt-get is outside the shipped stage and is not judged.
    assert upgrade_problems(_GOOD_DEBIAN, {"final"}) == []
    assert upgrade_problems(_GOOD_ALPINE, {"runner"}) == []
    assert stage_names(_GOOD_DEBIAN) == ["builder", "final"]


@pytest.mark.parametrize(
    ("text", "stage", "fragment"),
    [
        (_GOOD_DEBIAN.replace(_UPGRADE, ""), "final", "runs no apt-get upgrade"),
        (
            _GOOD_DEBIAN.replace("ARG PUBLISH_CACHE_BUST=\n", ""),
            "final",
            "no `ARG PUBLISH_CACHE_BUST`",
        ),
        (_GOOD_DEBIAN.replace('"${PUBLISH_CACHE_BUST}"', '"x"'), "final", "does not name"),
        (_GOOD_DEBIAN.replace(" --error-on=any", ""), "final", "--error-on=any"),
        (
            _GOOD_DEBIAN.replace("apt-get -o Acquire::Retries=0 install", "apt-get install"),
            "final",
            "runs with retries on",
        ),
        (
            _GOOD_DEBIAN + "RUN apt-get update && apt-get install -y xvfb\n",
            "final",
            "runs with retries on",
        ),
        (
            _GOOD_DEBIAN + "RUN apt-get -o Acquire::Retries=0 update && true\n",
            "final",
            "lacks --error-on=any",
        ),
        (_GOOD_DEBIAN.replace(" \\\n && rm -rf /var/lib/apt/lists/*", ""), "final", "apt lists"),
        (_GOOD_DEBIAN.replace(_UPGRADE, _UPGRADE + " || true"), "final", "fallback"),
        (_GOOD_DEBIAN.replace(_UPGRADE, _UPGRADE + " || :"), "final", "fallback"),
        (_GOOD_DEBIAN.replace("upgrade -y", "upgrade --simulate -y"), "final", "simulate"),
        (_GOOD_DEBIAN.replace("upgrade -y", "upgrade -s -y"), "final", "simulate"),
        (_GOOD_DEBIAN + "RUN apt install -y xvfb\n", "final", "runs with retries on"),
        (
            _GOOD_DEBIAN.replace("upgrade -y", "-o APT::Get::Simulate=true upgrade -y"),
            "final",
            "APT::Get::Simulate=true",
        ),
        (
            _GOOD_DEBIAN.replace("upgrade -y", "-oAPT::Get::Simulate=true upgrade -y"),
            "final",
            "only Acquire::Retries=0 is allowed",
        ),
        (
            _GOOD_DEBIAN.replace("upgrade -y", "--option=Debug::NoLocking=1 upgrade -y"),
            "final",
            "only Acquire::Retries=0 is allowed",
        ),
        (_GOOD_DEBIAN, "runner", "not found as a named FROM"),
        (_GOOD_ALPINE.replace("apk upgrade --no-cache", "apk upgrade"), "runner", "index cache"),
        (
            _GOOD_ALPINE.replace("apk upgrade --no-cache", "apk upgrade --no-cache || true"),
            "runner",
            "fallback",
        ),
    ],
)
def test_the_checker_rejects_a_broken_upgrade(text: str, stage: str, fragment: str) -> None:
    problems = upgrade_problems(text, {stage})
    assert any(fragment in problem for problem in problems), problems


def test_the_last_stage_checker_rejects_a_stage_appended_after_final() -> None:
    assert last_stage_problems(_GOOD_DEBIAN, {"final"}) == []
    appended = _GOOD_DEBIAN + f"FROM python:3.15.2-slim-trixie@sha256:{_DIGEST} AS debug\n"
    assert any("'debug'" in p for p in last_stage_problems(appended, {"final"}))
    unnamed = _GOOD_DEBIAN + f"FROM python:3.15.2-slim-trixie@sha256:{_DIGEST}\n"
    assert any("''" in p for p in last_stage_problems(unnamed, {"final"}))


def test_the_build_checker_rejects_an_unknown_target_and_a_missing_stage() -> None:
    def workflow(*targets: str) -> dict:
        steps = [
            {
                "uses": "docker/build-push-action@0",
                "name": f"build {t}",
                "with": {"file": "apps/cna-web/Dockerfile", "target": t},
            }
            for t in targets
        ]
        return {"jobs": {"web": {"steps": steps}}}

    assert any(
        "'builder'" in p for p in build_problems(workflow("runner", "builder"), "w", exact=False)
    )
    # Only the web stages are built here, so the exact check reports the Python images as missing too.
    assert any("expected exactly" in p for p in build_problems(workflow("runner"), "w", exact=True))
    assert build_problems(workflow("runner", "migrator"), "w", exact=False) == []


def test_the_shell_build_checker_rejects_a_build_without_the_cache_bust() -> None:
    def workflow(command: str) -> dict:
        return {"jobs": {"smoke": {"steps": [{"run": command}]}}}

    good = f'docker build --build-arg "{CACHE_BUST_VALUE}" -t cna:ci-test .'
    assert shell_build_problems(workflow(good), "w") == []
    bare = shell_build_problems(workflow("docker build -t x ."), "w")
    assert any("without --build-arg" in p for p in bare)
    continued = shell_build_problems(workflow("docker build \\\n  -t x \\\n  ."), "w")
    assert any("without --build-arg" in p for p in continued)
    other = (
        f'docker build --build-arg "{CACHE_BUST_VALUE}" -f apps/cna-web/Dockerfile --target deps .'
    )
    assert any("'deps'" in p for p in shell_build_problems(workflow(other), "w"))
