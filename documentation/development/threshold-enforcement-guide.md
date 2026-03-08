# Threshold Enforcement Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the final Azure hardening pass for threshold-based verification, promotion control, and certificate expiry enforcement.

---

## Added Controls

The platform now includes:
- explicit Azure Monitor health thresholds
- explicit Application Insights success-rate thresholds
- active Front Door promotion control execution
- certificate expiry threshold enforcement
- evidence summaries persisted in release manifests

---

## Design Intent

These changes are intended to raise the Azure delivery model from evidence collection to threshold-enforced operational control.
