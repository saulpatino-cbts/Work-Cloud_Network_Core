# Multi-stage Dockerfile — hardened
# Changes from original single-stage:
#   1. Pinned digest on base image (supply chain)
#   2. Builder stage: installs deps only, not full source (smaller final layer)
#   3. Non-root user (cna:cna uid/gid 1001) — CI smoke test verifies this
#   4. COPY --chown so files are owned by non-root user
#   5. Build arg CNA_VERSION injected at release time
#   6. HEALTHCHECK added (required for ECS/AKS task definitions)
#   7. .dockerignore referenced — see .dockerignore in repo root

# python:3.15.2-slim-trixie digest pinned 2026-11-12 (Python 3.15.2 on Debian 13.7 "trixie"; the digest
# python:3.15-slim pointed to that day). Moved from 3.14.10 because 390-scan-images failed the CLI and API images
# on CVE-2026-119170, fixed only in Python 3.14.11, for which no image exists. The tag names the Debian release on
# purpose, so a future Debian release under the floating tag cannot move the image to another distribution
# unnoticed (tests/unit/test_image_base_pins.py requires it). Dependabot's docker ecosystem watches every
# Dockerfile and bumps the digest on each FROM line; it does not offer the next Python minor, which is moved by
# hand (see .github/dependabot.yml). The `apt-get upgrade` in the final stage keeps the debs current between
# digest bumps (TODO.md T-727).
# uv, as a stage rather than an inline `COPY --from=<image>`: Dependabot's docker
# updater only reads `FROM` lines, so this is the line its weekly bump moves.
# Keep the version in step with the `uv==` pins in 300-test-codebase.yml.
FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS builder

ARG CNA_VERSION=dev
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz libcairo2 libpango-1.0-0 \
    libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Every Python image installs from uv.lock (TODO.md T-702): `uv export --locked`
# fails the build if the lock has drifted from pyproject.toml, and
# `--require-hashes` makes the install byte-for-byte the resolution that was
# reviewed. uv is copied in as a pinned, digest-verified binary and stays in
# the builder stage only. Dependencies first (cacheable layer), then the
# package itself with `--no-build-isolation` so the build backend is the
# hash-checked `build` group rather than whatever pip would fetch unpinned.
#
# PyYAML 6.0.3, the newest release, has no wheel for Python 3.15 yet (yaml/pyyaml#951, checked 2026-11-12), so it
# is built here from its hash-checked source archive. The build group goes in first so PyYAML is built with it
# (`--no-build-isolation-package`) rather than with a build backend fetched unpinned, and PYYAML_FORCE_LIBYAML=0
# builds the plain-Python version: this stage has no C compiler, and nothing here imports yaml.CLoader. Every
# other package installs as a prebuilt wheel. Drop both once a PyYAML release ships cp315 wheels (TODO.md T-726).
# The lockfile job in 300-test-codebase.yml runs the same commands.
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv export --locked --only-group build -o /tmp/build-requirements.txt \
 && uv pip install --system --no-cache --require-hashes --no-deps -r /tmp/build-requirements.txt \
 && uv export --locked --no-default-groups --no-emit-project -o /tmp/requirements.txt \
 && PYYAML_FORCE_LIBYAML=0 uv pip install --system --no-cache --require-hashes --no-deps --no-build-isolation-package pyyaml \
      --prefix=/install -r /tmp/requirements.txt
COPY cna/ cna/
RUN uv pip install --system --no-cache --no-deps --no-build-isolation --prefix=/install . \
 && rm -f /tmp/requirements.txt /tmp/build-requirements.txt

# ---- drawio fetch stage ----
# Pinned draw.io desktop release, verified by checksum before it can reach
# the final image. The export pipeline (cna/diagram_engine/export_pipeline.py)
# degrades to XML-only output without it — its own warning promises the CLI
# is available "inside the Docker container", which is made true here.
FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS drawio-fetch

ARG DRAWIO_VERSION=31.3.2
ARG DRAWIO_SHA256=725453f32ef7f2f63f8b50b374857a5c312e2aaabcf221cb0600332741ae1094

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && curl -fsSL -o /tmp/drawio.deb \
     "https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-amd64-${DRAWIO_VERSION}.deb" \
  && echo "${DRAWIO_SHA256}  /tmp/drawio.deb" | sha256sum -c -

# ---- final stage ----
# Named so tests/unit/test_image_security_upgrade.py can find the shipped stage; the build target is unchanged (it
# is the last stage, which 200-build-images.yml and 300-test-codebase.yml build without a `target`).
FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS final

ARG CNA_VERSION=dev
LABEL org.opencontainers.image.title="CNA Platform" \
      org.opencontainers.image.description="Cloud Network Assessment CLI" \
      org.opencontainers.image.version="${CNA_VERSION}" \
      org.opencontainers.image.source="https://github.com/saulpatino-cbts/Work-Cloud_Network_Core" \
      org.opencontainers.image.licenses="Proprietary"

# draw.io desktop CLI + xvfb for headless diagram export (.drawio -> .svg).
# The wrapper shadows /usr/bin/drawio on PATH and supplies xvfb-run,
# --no-sandbox, and a writable HOME — see the script for why each is
# required. `drawio --version` proves the whole chain at build time.
COPY --from=drawio-fetch /tmp/drawio.deb /tmp/drawio.deb
COPY --chmod=755 scripts/drawio-headless.sh /usr/local/bin/drawio
# Debian's security updates first, then the system deps for diagram generation and draw.io (runtime only), in
# one RUN, as in apps/cna-api/Dockerfile, so every apt-get in this shipped stage runs with the same settings.
# `apt-get upgrade` is deliberate (TODO.md T-727, which reverses T-702's "no upgrade" rule the way
# saulpatinojr/HCW-NetworkEyes_App T-741 did): the base is pinned by digest, but a Debian security upload reaches
# trixie-security days or weeks before the official image is rebuilt with it. On 2026-11-12 390-scan-images failed
# this image on CVE-2026-76844 and CVE-2026-85091 in zlib1g 1:1.3.dfsg+really1.3.1-1+b1, fixed in
# 1:1.3.dfsg+really1.3.1-1+deb13u1 in trixie-security, which no python base digest carried, so no digest bump
# could clear them. The upgrade closes that window; Dependabot's digest bump still moves the base. The cost: two
# builds of one commit on different days can differ in their Debian packages. The controls: 390-scan-images
# scans every published digest, and tests/unit/test_image_security_upgrade.py keeps this step in place.
# PUBLISH_CACHE_BUST is a per-run value (run id and attempt) that every image build in 200-build-images.yml and
# 300-test-codebase.yml passes. Naming it in the command changes this RUN's cache key on every run,
# so a rebuild of the same commit cannot reuse an older upgrade result from the Actions build cache after a newer
# security upload reached the mirrors. BuildKit then also rebuilds every later layer of this stage (the user,
# the copies, the pip removal), which costs build time and Actions cache space on each run; that is accepted.
# Unset on a local build, which is fine: the layers are then cached as usual. `--error-on=any` makes the update
# fail if any index (trixie-security above all) cannot be fetched, instead of succeeding with a warning and
# leaving the packages unupgraded. `Acquire::Retries=0` on every apt-get: apt below 3.0.4 (CVE-2026-109518) needs
# a download retry to slip an unverified package in, so that path stays closed whichever apt does the work (a
# mirror hiccup then fails the build instead of retrying).
ARG PUBLISH_CACHE_BUST=
RUN printf 'upgrade run: %s\n' "${PUBLISH_CACHE_BUST}" \
    && apt-get -o Acquire::Retries=0 update --error-on=any \
    && apt-get -o Acquire::Retries=0 upgrade -y --no-install-recommends \
    && apt-get -o Acquire::Retries=0 install -y --no-install-recommends \
    graphviz libcairo2 libpango-1.0-0 \
    libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    /tmp/drawio.deb xvfb xauth libasound2t64 \
    && rm -rf /var/lib/apt/lists/* /tmp/drawio.deb \
    && drawio --version

# Non-root user — uid/gid 1001
RUN groupadd --gid 1001 cna \
 && useradd --uid 1001 --gid cna --shell /bin/bash --create-home cna

WORKDIR /app
COPY --from=builder --chown=cna:cna /install /usr/local
COPY --chown=cna:cna . .

# Engagement data written here — must be writable by non-root user
RUN mkdir -p /app/engagements /app/output && chown -R cna:cna /app/engagements /app/output

# pip is unused at runtime and vendors CVE-carrying copies of msgpack and
# setuptools (declared in its own pip/_vendor/bom.cdx.json) that no
# `pip install` can replace — strip it from the shipped image, the same
# reasoning the web image uses to strip npm.
RUN python -m pip uninstall -y pip

# Commit the image was built from (200-build-images passes github.sha). The web
# tier compares it with the newest published build (Admin → Updates); empty
# for local builds, which report the running build as unknown.
ARG CNA_BUILD_SHA=
ENV CNA_BUILD_SHA=${CNA_BUILD_SHA}

USER cna

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD cna --help > /dev/null 2>&1 || exit 1

ENTRYPOINT ["cna"]
CMD ["--help"]
