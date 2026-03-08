# Release Safety Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the latest operational safety controls for hosted CNA Platform delivery.

---

## Added Controls

The deployment workflow now supports:
- release and rollback modes
- previous image references for rollback execution
- deployment manifest artifact generation

The security layer now includes an initial API ingress governance contract.

---

## Design Intent

These changes create a more reviewable and recoverable release model while establishing a starting point for network isolation controls.
