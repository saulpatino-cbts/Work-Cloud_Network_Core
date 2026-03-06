# 22 — Network Isolation, Rollback, and Release Provenance

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the next operational hardening pass for hosted CNA Platform delivery.

---

## Objective

`22-network-isolation-rollback-and-release-provenance` introduces initial network governance controls, explicit rollback workflow inputs, and deployment provenance artifacts.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/security` | Adds initial ingress governance resources and API CIDR control contract |
| `.github/workflows/deploy-azure-runtime.yml` | Adds rollback mode, previous image inputs, and deployment manifest provenance artifact |

---

## Hardening Scope

This pass adds:
- initial ingress governance through NSG resources
- explicit rollback execution mode
- previous image input support for rollback actions
- deployment manifest generation for release provenance tracking

---

## Remaining Gaps

Future work should still address:
- true private network integration for Container Apps
- WAF or edge ingress controls
- signed provenance attestations
- automated rollback decisioning
- environment-specific release catalogs
