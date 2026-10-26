#!/usr/bin/env bash
# Scan one container image with Docker Scout for fixable CRITICAL/HIGH CVEs.
#
# This is a LOCAL developer helper. CI no longer runs Docker Scout: it needs a Docker
# account entitled to Scout, which the keyless OIDC identity of 200-build-images does
# not have. CI scans the published digests with Anchore Grype instead, after every
# main publish (390-scan-images.yml). This script applies the same policy, fixable
# critical/high findings fail, with Docker Scout from a machine signed in to an
# entitled Docker account:
#
#     only-severities: critical,high   only-fixed: true   exit-code: true
#
# so you can scan an image you built locally, or any published digest, before pushing.
# It is a different scanner and vulnerability database from 390's, so the findings
# can differ; 390 is the check of record.
#
# Usage:
#   scripts/ci/scout_scan.sh <image-ref>
#
# Examples:
#   scripts/ci/scout_scan.sh cna-web:dev                     # a local build
#   scripts/ci/scout_scan.sh docker.io/<namespace>/cna@sha256:<64>   # a digest
#
# Exit code: 0 = no fixable critical/high CVEs; non-zero = Scout found some
# (or a prerequisite is missing). Mirrors the policy of 390's gate so this script
# is safe to use in a pre-push hook or a Makefile target.
#
# Prerequisites:
#   - Docker Desktop / Engine running.
#   - The Docker Scout CLI plugin. If it is missing, install it once with:
#       curl -fsSL https://raw.githubusercontent.com/docker/scout-cli/main/install.sh | sh -s --
#     (see https://docs.docker.com/scout/install/). On Docker Desktop it is
#     usually already bundled.
set -euo pipefail

REF="${1:-}"
if [ -z "$REF" ]; then
  echo "error: scout_scan.sh expects an image reference, e.g. 'cna-web:dev' or 'docker.io/<namespace>/cna@sha256:<64>'." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker CLI not found. Install Docker Desktop/Engine first (https://docs.docker.com/get-docker/)." >&2
  exit 2
fi

if ! docker scout version >/dev/null 2>&1; then
  echo "error: the Docker Scout CLI plugin is not installed." >&2
  echo "       Install it once with:" >&2
  echo "         curl -fsSL https://raw.githubusercontent.com/docker/scout-cli/main/install.sh | sh -s --" >&2
  echo "       See https://docs.docker.com/scout/install/ for details." >&2
  exit 2
fi

echo "Scanning ${REF} for fixable CRITICAL/HIGH CVEs (same gate as 200-build-images.yml)..."
# --only-severity critical,high and --only-fixed match the CI action inputs;
# --exit-code makes Scout return non-zero when any such CVE is present.
docker scout cves "$REF" \
  --only-severity critical,high \
  --only-fixed \
  --exit-code
