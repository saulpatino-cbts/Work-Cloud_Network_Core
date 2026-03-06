# Deployment Promotion Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first environment promotion model for the hosted CNA Platform.

---

## Promotion Inputs

The deploy workflow currently accepts:
- target environment
- API image reference
- worker image reference

---

## Design Intent

This workflow creates the first controlled path from published container images to Terraform-applied Azure runtime updates.

It is intentionally manual for the first release model.
