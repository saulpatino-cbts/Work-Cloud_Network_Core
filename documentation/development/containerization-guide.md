# Containerization Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first containerization approach for hosted CNA Platform applications.

---

## Images

Initial images:
- `cna-api`
- `cna-worker`

---

## Design Intent

The first containerization layer is intentionally minimal and exists to establish a path from application code to deployable runtime images.

Later work should align these images with shared project dependencies, optimized build layering, and CI/CD publishing workflows.
