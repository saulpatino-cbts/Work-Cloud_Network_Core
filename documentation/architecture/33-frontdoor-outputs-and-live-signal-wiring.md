# 33 — Front Door Outputs and Live Signal Wiring

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the control-plane integration pass that exposes richer Front Door outputs and wires verification evidence to live platform context.

---

## Objective

`33-frontdoor-outputs-and-live-signal-wiring` expands security module outputs for Front Door and certificate resources, persists that platform context into deployment manifests, and rewires verification evidence generation to consume actual deployment outputs instead of generic local placeholders.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/security/outputs.tf` | Exposes Front Door profile, endpoint, origin group, route, custom domain, firewall policy, and secret outputs |
| `.github/workflows/deploy-azure-runtime.yml` | Exports Terraform outputs after apply, records platform context in the deployment manifest, and uses that context when generating verification evidence |

---

## Assurance Impact

This pass improves assurance by:
- exposing edge and certificate resource identities needed for external verification wiring
- persisting live platform context into release manifests
- making verification evidence reference deployed platform resources instead of anonymous simulated artifacts

---

## Remaining Gaps

Future work should still address:
- replacing file generation with direct Azure Monitor, Application Insights, Front Door, and certificate system API queries
- executing real staged traffic movement instead of recording staged-promotion pass state
- tying certificate rotation evidence to actual renewal execution and expiry thresholds
