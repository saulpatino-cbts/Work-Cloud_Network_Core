# 20 — Runtime and Delivery Hardening

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document captures the first code hardening pass that closes critical runtime and deployment gaps in the hosted CNA Platform.

---

## Objective

`20-runtime-and-delivery-hardening` strengthens Azure Container Apps runtime definition and deployment controls so the platform moves closer to production-grade operational quality.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/compute` | Adds registry configuration, probes, scaling controls, secret-backed env support, and runtime input contracts |
| `.github/workflows/deploy-azure-runtime.yml` | Adds deployment concurrency protection and scheduled drift detection scaffold |

---

## Hardening Areas

The hardening pass adds:
- registry authentication contract for Container Apps
- configurable scale bounds
- HTTP health probes for the API
- secret-backed and plain environment variable support
- deployment concurrency protection
- drift detection workflow scaffold

---

## Remaining Gaps

Future work should still address:
- GitHub OIDC federation for Azure authentication
- explicit remote backend storage configuration
- container vulnerability scanning and policy enforcement
- rollback automation
- private networking and egress restriction strategy
