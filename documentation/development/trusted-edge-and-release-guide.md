# Trusted Edge and Release Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the latest hardening controls added for ingress protection and release trust.

---

## Added Controls

The runtime and delivery layers now support:
- internal-only Container Apps ingress option
- Front Door and WAF scaffolding
- signed deployment manifest attestation
- environment-scoped release catalog artifacts

---

## Design Intent

These changes move the platform closer to controlled ingress, stronger provenance, and safer rollback selection.
