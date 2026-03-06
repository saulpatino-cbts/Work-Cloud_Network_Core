# Private Connectivity Completion Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the infrastructure completion pass for private Azure connectivity.

---

## Added Controls

The platform now includes:
- dedicated VNets per environment
- delegated Container Apps infrastructure subnet integration
- reserved private endpoint subnet per environment
- internal-only Container Apps runtime deployment mode

---

## Design Intent

These changes establish actual network topology in code rather than relying only on delivery and edge-control scaffolding.
