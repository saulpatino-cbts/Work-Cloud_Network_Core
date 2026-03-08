# 35 — Direct Azure Queries and Live Evidence Collection

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first execution-oriented pass that replaces intent-marked evidence generation with direct Azure command execution for monitoring and certificate data.

---

## Objective

`35-direct-azure-queries-and-live-evidence-collection` updates the verification workflow to execute direct Azure CLI queries for Azure Monitor, Application Insights, Front Door route state, and Key Vault certificate information.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `.github/workflows/deploy-azure-runtime.yml` | Executes direct Azure CLI and REST queries to collect health, telemetry, route, and certificate evidence |

---

## Assurance Impact

This pass improves assurance by:
- replacing intent-marked evidence with direct Azure command execution
- grounding release evidence in actual platform query results
- establishing a base pattern for future evidence evaluation logic

---

## Remaining Gaps

Future work should still address:
- evaluating returned evidence content instead of only checking file existence
- executing real traffic-weight changes rather than only reading Front Door route state
- tying certificate rotation approval to renewal timing and expiration thresholds
