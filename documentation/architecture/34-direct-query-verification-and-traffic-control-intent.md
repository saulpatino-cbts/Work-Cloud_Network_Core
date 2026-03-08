# 34 — Direct Query Verification and Traffic Control Intent

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the next control-plane pass that moves verification language from generic evidence generation toward direct platform query intent and traffic-control execution intent.

---

## Objective

`34-direct-query-verification-and-traffic-control-intent` updates the verification workflow to explicitly model direct-query evidence for Azure Monitor, Application Insights, and certificate monitoring, and to represent staged promotion as a traffic-shift control action.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Adds direct-query intent markers for health and telemetry evidence, and models staged promotion as a traffic-shift action |

---

## Assurance Impact

This pass improves the delivery model by:
- making verification semantics explicitly query-oriented rather than placeholder-oriented
- distinguishing traffic-shift execution intent from passive promotion state recording
- carrying expiry-threshold language into certificate rotation evidence

---

## Remaining Gaps

Future work should still address:
- replacing intent-mode evidence files with actual Azure CLI or API query execution
- implementing real Front Door or application traffic-weight changes
- binding certificate rotation evidence to actual renewal jobs and threshold evaluations
