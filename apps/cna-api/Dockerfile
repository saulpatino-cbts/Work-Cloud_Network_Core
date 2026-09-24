# python:3.14-slim digest pinned — see root Dockerfile for the same pattern.
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2 AS builder

WORKDIR /build

# libpq-dev + gcc needed for psycopg2 compilation; builder-only, not in final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
  && rm -rf /var/lib/apt/lists/*

# Install the cna package with its API extra. `.[api]` resolves the core
# dependencies plus fastapi/uvicorn/psycopg2-binary and the three azure-mgmt-*
# enrichment packages the API exercises, from the single source of truth in
# pyproject.toml — no hand-written pip list to drift out of sync (PY-021). The
# heavier deps (diagrams/matplotlib/pandas/weasyprint) come in as core deps;
# that is accepted and removes the silent enrichment degradation (IMG-010).
COPY pyproject.toml .
COPY cna/ cna/
COPY apps/cna-api/ apps/cna-api/

RUN pip install --no-cache-dir --prefix=/install ".[api]"

# ---- drawio fetch stage ----
# Pinned draw.io desktop release, verified by checksum before it can reach
# the final image. Used headlessly (see scripts/drawio-headless.sh) so the
# encyclopedia report's diagram SVGs render instead of silently degrading.
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2 AS drawio-fetch

ARG DRAWIO_VERSION=31.3.2
ARG DRAWIO_SHA256=725453f32ef7f2f63f8b50b374857a5c312e2aaabcf221cb0600332741ae1094

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && curl -fsSL -o /tmp/drawio.deb \
     "https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-amd64-${DRAWIO_VERSION}.deb" \
  && echo "${DRAWIO_SHA256}  /tmp/drawio.deb" | sha256sum -c -

# ---- final stage ----
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

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
RUN apt-get update \
 && apt-get -y upgrade \
 && apt-get install -y --no-install-recommends /tmp/drawio.deb xvfb xauth libasound2t64 \
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
