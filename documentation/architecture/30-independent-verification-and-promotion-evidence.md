# 30 — Independent Verification and Promotion Evidence

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the final trust-model pass for deployment verification and promotion evidence.

---

## Objective

`30-independent-verification-and-promotion-evidence` introduces a separate verification stage after apply, requires independent verification and promotion readiness evidence in release catalog entries, and updates rollback selection to depend on those signals.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Separates verification from apply, records independent verification and promotion evidence, and requires those signals for rollback eligibility |

---

## Governance Impact

This pass improves the trust model by:
- separating apply-time execution from post-apply verification flow
- recording independent verification and promotion readiness signals
- requiring those signals before a release can be used as a rollback target

---

## Remaining Gaps

Future work should still address:
- external verification systems beyond in-pipeline staged evidence
- automated canary or staged promotion signals from runtime telemetry
- certificate rotation automation and expiry monitoring
