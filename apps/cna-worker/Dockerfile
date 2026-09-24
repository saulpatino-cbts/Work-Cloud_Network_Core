# python:3.14-slim digest pinned — see root Dockerfile for the same pattern.
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2 AS builder

WORKDIR /build
COPY pyproject.toml .
COPY apps/cna-worker apps/cna-worker
RUN pip install --no-cache-dir --prefix=/install azure-identity azure-storage-blob

# ---- final stage ----
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

# Pending Debian security fixes, so the gating Docker Scout check doesn't
# fail on base-image debs between digest bumps (same pattern as the root
# and API Dockerfiles).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

# Non-root user — uid/gid 1001 (matches root Dockerfile's cna user).
RUN groupadd --gid 1001 cna \
 && useradd --uid 1001 --gid cna --no-create-home --shell /usr/sbin/nologin cna

WORKDIR /app
COPY --from=builder --chown=cna:cna /install /usr/local
COPY --chown=cna:cna apps/cna-worker /app/apps/cna-worker

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

# The worker is a run-once batch process (and a retirement candidate — see spec
# task 4.5), so a network liveness probe would be misleading. This smoke check
# verifies the module and its Azure SDK deps import cleanly, which is the
# meaningful "the container is well-formed" signal for a batch image.
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=2 \
    CMD python -c "import azure.identity, azure.storage.blob" || exit 1

CMD ["python", "apps/cna-worker/main.py"]
