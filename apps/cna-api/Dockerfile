# python:3.15.2-slim-trixie digest pinned 2026-11-12 (Python 3.15.2 on Debian 13.7 "trixie"; moved from 3.14.10
# for CVE-2026-119170) — see the root Dockerfile for why, and for why the tag names the Debian release. Every
# Python FROM line in both Dockerfiles shares this one digest (tests/unit/test_image_base_pins.py).
# uv, as a stage rather than an inline `COPY --from=<image>`: Dependabot's docker
# updater only reads `FROM` lines, so this is the line its weekly bump moves.
# Keep the version in step with the `uv==` pins in 300-test-codebase.yml.
FROM ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv

FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS builder

WORKDIR /build

# Install the cna package with its API extra. `.[api]` resolves the core
# dependencies plus fastapi/uvicorn/psycopg2-binary and the three azure-mgmt-*
# enrichment packages the API exercises, from the single source of truth in
# pyproject.toml — no hand-written pip list to drift out of sync (PY-021). The
# heavier deps (diagrams/matplotlib/pandas/weasyprint) come in as core deps;
# that is accepted and removes the silent enrichment degradation (IMG-010).
#
# Installed from uv.lock (TODO.md T-702) — see the root Dockerfile for the
# pattern: `uv export --locked` fails on lock drift, `--require-hashes` pins
# every wheel, the `build` group is the hash-checked build backend, and uv
# never leaves the builder stage. Every package is a prebuilt cp315 (or abi3 or
# pure-Python) manylinux wheel (psycopg2-binary included), so no compiler or
# libpq-dev is needed, with one exception: PyYAML 6.0.3 has no cp315 wheel yet
# (yaml/pyyaml#951, checked 2026-11-12) and is built from its hash-checked
# source archive as plain Python, with the hash-checked build group installed
# first; the root Dockerfile says why. Drop the PyYAML flags once a PyYAML
# release ships cp315 wheels (TODO.md T-726).
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv export --locked --only-group build -o /tmp/build-requirements.txt \
 && uv pip install --system --no-cache --require-hashes --no-deps -r /tmp/build-requirements.txt \
 && uv export --locked --no-default-groups --no-emit-project --extra api -o /tmp/requirements.txt \
 && PYYAML_FORCE_LIBYAML=0 uv pip install --system --no-cache --require-hashes --no-deps --no-build-isolation-package pyyaml \
      --prefix=/install -r /tmp/requirements.txt
COPY cna/ cna/
COPY apps/cna-api/ apps/cna-api/
RUN uv pip install --system --no-cache --no-deps --no-build-isolation --prefix=/install . \
 && rm -f /tmp/requirements.txt /tmp/build-requirements.txt

# ---- drawio fetch stage ----
# Pinned draw.io desktop release, verified by checksum before it can reach
# the final image. Used headlessly (see scripts/drawio-headless.sh) so the
# encyclopedia report's diagram SVGs render instead of silently degrading.
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

# Non-root user — uid/gid 1001 (matches root Dockerfile's cna user).
RUN groupadd --gid 1001 cna \
 && useradd --uid 1001 --gid cna --no-create-home --shell /usr/sbin/nologin cna

# draw.io desktop CLI + xvfb for headless diagram SVG export (Electron needs
# an X display even for --export). The wrapper shadows /usr/bin/drawio on
# PATH and supplies xvfb-run, --no-sandbox, and a writable HOME — see the
# script for why each is required. `drawio --version` proves the whole
# chain (deb deps, xvfb, wrapper) at build time rather than at first render.
COPY --from=drawio-fetch /tmp/drawio.deb /tmp/drawio.deb
COPY --chmod=755 scripts/drawio-headless.sh /usr/local/bin/drawio
# Debian's security updates first (`apt-get upgrade`, deliberate: a security upload reaches trixie-security
# before the official base image is rebuilt with it, and on 2026-11-12 no python base digest carried the zlib1g
# fix for CVE-2026-76844 and CVE-2026-85091; see the root Dockerfile and TODO.md T-727), then these packages.
# `Acquire::Retries=0` and `--error-on=any` as in the root Dockerfile. PUBLISH_CACHE_BUST (run id and attempt,
# passed by 200-build-images.yml and 300-test-codebase.yml), named in the command, keeps a later run of the same
# commit from reusing a cached upgrade result; BuildKit then rebuilds this RUN and every later layer of the stage
# (build time and Actions cache churn, accepted; see the root Dockerfile).
ARG PUBLISH_CACHE_BUST=
RUN printf 'upgrade run: %s\n' "${PUBLISH_CACHE_BUST}" \
 && apt-get -o Acquire::Retries=0 update --error-on=any \
 && apt-get -o Acquire::Retries=0 upgrade -y --no-install-recommends \
 && apt-get -o Acquire::Retries=0 install -y --no-install-recommends /tmp/drawio.deb xvfb xauth libasound2t64 \
      graphviz libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
      libharfbuzz0b libgdk-pixbuf-2.0-0 \
 && rm -rf /var/lib/apt/lists/* /tmp/drawio.deb \
 && drawio --version

WORKDIR /app
COPY --from=builder --chown=cna:cna /install /usr/local
COPY --chown=cna:cna cna/ /app/cna/
COPY --chown=cna:cna apps/cna-api/ /app/apps/cna-api/

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

# Liveness for orchestrators (ECS/AKS/Container Apps): the API answers on 8080
# once uvicorn is up. Uses the stdlib (no curl, and pip is stripped).
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5).status < 500 else 1)" || exit 1

# Non-root can't bind <1024; the appliances' compute module targets this port
# (`api_target_port` in the Azure appliance's Terraform).
CMD ["uvicorn", "apps.cna-api.main:app", "--host", "0.0.0.0", "--port", "8080"]
