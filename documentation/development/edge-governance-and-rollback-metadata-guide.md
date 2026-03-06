# Edge Governance and Rollback Metadata Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the governance-focused correction pass for external exposure and rollback decisioning.

---

## Added Controls

The platform now includes:
- Front Door custom-domain DNS zone integration inputs
- explicit TLS certificate policy settings for custom domains
- approval and health metadata recorded in release catalog entries
- rollback selection filtered to approved and healthy releases

---

## Design Intent

These changes improve operational governance without changing the core private architecture already established in earlier passes.
