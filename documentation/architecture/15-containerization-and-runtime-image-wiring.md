# 15 — Containerization and Runtime Image Wiring

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first containerization layer for the hosted CNA Platform applications.

---

## Objective

`15-containerization-and-runtime-image-wiring` introduces container build definitions for `cna-api` and `cna-worker` so the hosted runtime can move away from placeholder images.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `apps/cna-api/Dockerfile` | Build definition for hosted API runtime image |
| `apps/cna-worker/Dockerfile` | Build definition for hosted worker runtime image |

---

## Current Position

This workstream creates the first container build artifacts for the hosted application layer.

A later workstream should add:
- dependency optimization from the main project definition
- image publishing workflow to a registry
- Container Apps image replacement in Terraform
- environment-specific image tags
- vulnerability scanning and image signing
