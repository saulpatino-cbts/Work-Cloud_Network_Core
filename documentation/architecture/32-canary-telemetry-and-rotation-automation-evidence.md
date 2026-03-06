# 32 — Canary Telemetry and Rotation Automation Evidence

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the assurance extension pass for canary telemetry, staged promotion, and certificate rotation evidence.

---

## Objective

`32-canary-telemetry-and-rotation-automation-evidence` adds canary telemetry, staged promotion, and certificate rotation evidence fields to release manifests and requires those signals for rollback eligibility.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Adds canary telemetry, staged promotion, and certificate rotation evidence artifacts and requires those signals for rollback eligibility |

---

## Assurance Impact

This pass improves assurance by:
- tracking canary telemetry as release evidence
- capturing staged promotion readiness as a separate trust signal
- requiring certificate rotation automation evidence in release governance

---

## Remaining Gaps

Future work should still address:
- replacing simulated monitoring artifacts with real service integrations
- wiring staged traffic shifts to actual Front Door or Container Apps traffic controls
- driving certificate rotation evidence from live automation workflows
