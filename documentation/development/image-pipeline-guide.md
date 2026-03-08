# Image Pipeline Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first container image publication workflow for hosted CNA Platform services.

---

## Workflow Output

The image workflow builds and publishes:
- `cna-api`
- `cna-worker`

The publication target is GitHub Container Registry.

---

## Design Intent

This workflow creates the first automated path from source code changes to hosted runtime images.

It is the bridge between local container definitions and Terraform-managed runtime deployment.
