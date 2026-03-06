# Certificate and Validation Evidence Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the governance pass for certificate lifecycle control and release validation evidence.

---

## Added Controls

The platform now includes:
- Key Vault-backed Front Door customer certificate support
- validation check metadata in release catalog manifests
- rollback filtering that requires successful validation evidence

---

## Design Intent

These changes move the delivery model closer to evidence-based recovery decisions and stronger edge certificate governance.
