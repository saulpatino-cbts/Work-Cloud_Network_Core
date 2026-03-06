# Independent Verification Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the trust-model pass for independent verification and promotion evidence.

---

## Added Controls

The platform now includes:
- a separate verification stage after infrastructure apply
- independent verification and promotion-readiness fields in release manifests
- rollback filtering that requires independent verification evidence

---

## Design Intent

These changes improve separation between deployment execution and release trust decisions.
