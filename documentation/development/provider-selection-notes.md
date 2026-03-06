# Provider Selection Notes

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document captures the current provider strategy for the hosted CNA Platform.

---

## Shared Rule

The CNA Platform uses a shared workload model and provider-specific realization.

The application layer should remain as cloud-neutral as practical. Infrastructure realization should use native cloud services where they provide clear operational advantage.

---

## Provider Defaults

| Concern | Default Position |
|---|---|
| IaC | Terraform |
| AWS AI | Bedrock |
| Azure AI | Azure OpenAI |
| Runtime | Managed containers |
| Storage | Native object storage |
| Delivery | Static website + CDN |
| Secrets | Native cloud secret store |

---

## Why Not Full Cloud-Abstraction

A fully abstracted infrastructure model would hide important operational and security differences between AWS and Azure.

Instead, the CNA Platform should keep a shared capability model while allowing provider-specific implementations that remain explicit and reviewable.
