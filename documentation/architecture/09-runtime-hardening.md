# 09 — Runtime Hardening

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first security hardening slice for the hosted CNA Platform on Azure.

---

## Objective

`09-runtime-hardening` strengthens the hosted runtime by moving key runtime values into Key Vault-backed storage and formalizing the next security posture improvements.

---

## Delivered Module

| Module | Responsibility |
|---|---|
| `providers/azure/security` | Key Vault secret materialization for runtime values and initial hardening controls |

---

## Hardening Scope

This workstream adds:
- Key Vault secret storage for runtime values
- stronger secret-handling posture for AI and telemetry configuration
- groundwork for later secret references from runtime apps

---

## Current Position

This is a hardening bridge between bootstrap runtime wiring and full production hardening.

A later workstream should add:
- direct Key Vault secret references in runtime app definitions
- user-assigned identity attachment on runtime apps
- deeper RBAC reduction and scope tightening
- diagnostic settings, alert rules, and dashboards
- network restriction strategy for Key Vault, storage, and AI resources
