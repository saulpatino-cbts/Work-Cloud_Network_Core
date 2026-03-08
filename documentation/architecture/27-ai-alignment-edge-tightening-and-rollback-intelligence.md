# 27 — AI Alignment, Edge Tightening, and Rollback Intelligence

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the correction pass that aligns private connectivity to actual AI resources, improves Front Door edge behavior, and strengthens rollback target discovery logic.

---

## Objective

`27-ai-alignment-edge-tightening-and-rollback-intelligence` replaces placeholder OpenAI private endpoint wiring with the real Azure OpenAI account resource ID, adds Front Door custom-domain and managed-certificate support, and improves rollback selection to choose the latest recorded release entry rather than an undifferentiated latest catalog file.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/ai` | Exposes Azure OpenAI account resource ID |
| `providers/azure/security` | Uses actual Azure OpenAI account ID for private endpoint, adds Front Door custom domain support, and tightens route/domain association logic |
| `environments/azure/dev` | Passes Azure OpenAI account ID into security module |
| `environments/azure/prod` | Passes Azure OpenAI account ID into security module |
| `.github/workflows/deploy-azure-runtime.yml` | Improves rollback discovery to select the latest release entry from the environment catalog |

---

## Architecture Impact

This pass corrects three high-value issues:
- AI private connectivity now targets the real OpenAI resource
- edge configuration supports custom domain and managed certificate patterns
- rollback logic now prefers release records instead of blindly trusting latest state

---

## Remaining Gaps

Future work should still address:
- real DNS zone resource integration for Front Door custom domains
- certificate lifecycle governance beyond managed defaults
- rollback selection policies based on health or approval metadata
