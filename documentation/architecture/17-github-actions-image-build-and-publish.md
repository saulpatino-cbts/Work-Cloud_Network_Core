# 17 — GitHub Actions Image Build and Publish

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first automated image pipeline for hosted CNA Platform services.

---

## Objective

`17-github-actions-image-build-and-publish` introduces a GitHub Actions workflow that builds and publishes `cna-api` and `cna-worker` images to GitHub Container Registry.

---

## Delivered Workflow

| Workflow | Responsibility |
|---|---|
| `.github/workflows/build-and-publish-images.yml` | Build and publish container images for hosted runtime services |

---

## Trigger Model

The workflow runs on:
- pushes to `main`
- changes under `apps/cna-api/**`
- changes under `apps/cna-worker/**`
- changes to `pyproject.toml`
- manual workflow dispatch

---

## Published Images

The workflow publishes:
- `ghcr.io/<owner>/cna-api`
- `ghcr.io/<owner>/cna-worker`

Tags include:
- `latest`
- commit SHA tag

---

## Next Steps

A later workstream should add:
- image signing
- vulnerability scanning
- deployment workflow chaining
- environment-specific release tagging
- automatic Terraform deployment consumption
