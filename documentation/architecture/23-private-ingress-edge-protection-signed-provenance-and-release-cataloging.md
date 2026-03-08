# 23 — Private Ingress, Edge Protection, Signed Provenance, and Release Cataloging

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the next hardening pass for production-grade hosted delivery controls.

---

## Objective

`23-private-ingress-edge-protection-signed-provenance-and-release-cataloging` introduces internal-only Container Apps ingress support, Front Door and WAF scaffolding, signed provenance attestations, and environment-scoped release catalog artifacts.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/compute` | Adds internal-only Container Apps environment and ingress toggle |
| `providers/azure/security` | Adds Azure Front Door and WAF governance scaffold |
| `.github/workflows/deploy-azure-runtime.yml` | Adds signed provenance attestation and environment-scoped release catalog artifact flow |

---

## Hardening Scope

This pass adds:
- internal-only Container Apps environment option
- edge protection scaffold with Front Door and WAF resources
- GitHub artifact attestation for deployment manifest provenance
- environment-scoped release catalog artifact pattern for rollback targeting

---

## Remaining Gaps

Future work should still address:
- full private endpoint and VNet integration for runtime dependencies
- origin routing and custom domain binding for Front Door
- durable release catalog persistence outside workflow artifacts
- automated rollback target discovery
