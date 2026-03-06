# 25 — VNet Integration and Private Connectivity Completion

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the infrastructure completion pass that converts the hosted CNA Platform from control-plane intent into concrete network topology design.

---

## Objective

`25-vnet-integration-and-private-connectivity-completion` introduces dedicated virtual networks, delegated Container Apps infrastructure subnets, and private endpoint subnet foundations so the Azure runtime architecture reflects real private connectivity design.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/compute` | Supports delegated subnet integration for Container Apps managed environment |
| `environments/azure/dev` | Adds VNet, delegated Container Apps subnet, and private endpoint subnet |
| `environments/azure/prod` | Adds VNet, delegated Container Apps subnet, and private endpoint subnet |

---

## Architecture Impact

This pass adds:
- environment-specific virtual network topology
- delegated subnet for Container Apps environment infrastructure
- dedicated subnet reserved for private endpoints
- internal-only Container Apps environment backed by explicit subnet integration

---

## Remaining Gaps

Future work should still address:
- actual private endpoint resources for Storage, Key Vault, and AI services
- private DNS zone wiring
- custom domain and certificate lifecycle for Front Door
- release catalog intelligence beyond latest known good state
