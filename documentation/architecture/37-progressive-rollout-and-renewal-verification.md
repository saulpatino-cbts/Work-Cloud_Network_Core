# 37 — Progressive Rollout and Renewal Verification

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the Azure A+ completion pass for progressive rollout control and renewal-aware certificate verification.

---

## Objective

`37-progressive-rollout-and-renewal-verification` adds weighted promotion actions for Front Door origins and requires renewal or rotation evidence when certificate expiry falls inside the configured threshold window.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Adds weighted origin promotion updates, certificate renewal verification checks, and evidence summary fields for rollout weights and renewal state |

---

## Assurance Impact

This pass improves assurance by:
- moving from coarse promotion to progressive weighted rollout control
- requiring certificate renewal or rotation evidence when expiry thresholds are breached
- recording rollout-weight and renewal-verification signals in the release catalog

---

## Remaining Gaps

Future work should still address:
- aligning origin identifiers with fully provisioned canary/primary origin topology in Terraform
- invoking a formal certificate renewal automation workflow rather than fallback import semantics
- adding multi-step rollout progression with pause-and-observe stages
