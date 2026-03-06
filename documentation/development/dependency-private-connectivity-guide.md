# Dependency Private Connectivity Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the dependency-side private connectivity hardening pass for the hosted CNA Platform.

---

## Added Controls

The platform now includes:
- private DNS zones for core dependency patterns
- VNet links for private name resolution
- private endpoints for storage and Key Vault
- Azure OpenAI private connectivity scaffold

---

## Design Intent

These changes extend private connectivity from runtime topology into dependency resolution and service access patterns.
