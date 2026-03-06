# Terraform Deployment Safety Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document describes the first deployment safety model for the hosted CNA Platform.

---

## Safety Controls

The deployment workflow now includes:
- `terraform fmt -check`
- `terraform validate`
- `terraform plan`
- apply only after plan completion
- production approval through environment protection

---

## Design Intent

This workflow separates verification from deployment so release promotion becomes safer and more reviewable.

It is the first operational hardening step for Terraform-based Azure delivery.
