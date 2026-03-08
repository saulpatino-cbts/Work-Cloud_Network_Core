# 36 — Threshold-Enforced Verification and Promotion Control

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the final Azure hardening pass for threshold-based evidence evaluation, active promotion control, and certificate expiry gating.

---

## Objective

`36-threshold-enforced-verification-and-promotion-control` adds explicit pass/fail thresholds for Azure Monitor and Application Insights evidence, executes an active Front Door route update as a promotion action, and enforces certificate expiry windows before release evidence can pass.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Adds threshold constants, evaluates health and telemetry values, executes a Front Door route update, and gates release approval on certificate expiry windows |

---

## Assurance Impact

This pass improves assurance by:
- converting direct Azure query results into explicit pass/fail decisions
- moving staged promotion from observation into active control execution
- making certificate rotation evidence depend on real expiry timing thresholds

---

## Remaining Gaps

Future work should still address:
- more precise Front Door traffic-weight manipulation rather than route-level update semantics
- explicit renewal workflow invocation before certificate expiry breaches
- richer multi-stage promotion orchestration beyond single-step route control
