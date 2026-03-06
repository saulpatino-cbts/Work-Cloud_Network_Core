# 31 — External Validation Signals and Monitoring Evidence

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the next assurance pass that extends release verification with external health and certificate monitoring signals.

---

## Objective

`31-external-validation-signals-and-monitoring-evidence` adds external-health and certificate-monitoring evidence fields to release manifests and requires those signals for rollback eligibility.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Adds external health and certificate monitoring evidence fields, stages simulated external verifier artifacts, and requires those signals for rollback eligibility |

---

## Assurance Impact

This pass improves assurance by:
- distinguishing external health validation from internal verification checks
- tracking certificate monitoring evidence for release trust
- requiring monitoring-backed evidence during rollback candidate selection

---

## Remaining Gaps

Future work should still address:
- integration with real external monitoring platforms rather than simulated artifacts
- canary telemetry and staged traffic promotion evidence
- automated certificate rotation execution linked to monitoring thresholds
