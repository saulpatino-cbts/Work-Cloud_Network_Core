# Runtime Hardening Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the first runtime hardening pass for hosted CNA Platform infrastructure.

---

## Added Controls

The compute runtime now supports:
- registry configuration
- health probes for the API
- configurable scaling
- secret-backed application configuration
- plain environment variable injection

The deployment workflow now includes concurrency protection and a first drift detection scaffold.

---

## Design Intent

These changes reduce implicit runtime behavior and increase operational control over hosted application delivery.
