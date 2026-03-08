# Terraform Structure Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-05

This document defines the Terraform layout for the hosted CNA Platform.

---

## Design Goal

Terraform is used to maintain one platform architecture model with provider-specific implementations for AWS and Azure.

The workload contract is shared; resource implementation is provider-specific.

---

## Directory Layout

```text
infra/
└── terraform/
    ├── modules/
    │   ├── ingress/
    │   ├── storage/
    │   ├── compute/
    │   ├── queue/
    │   ├── metadata/
    │   ├── ai/
    │   ├── presentation/
    │   ├── identity/
    │   └── observability/
    ├── providers/
    │   ├── aws/
    │   └── azure/
    └── environments/
        ├── aws/
        │   ├── dev/
        │   └── prod/
        └── azure/
            ├── dev/
            └── prod/
```

---

## Module Contract

Each top-level module represents a workload capability, not a cloud-specific product.

Examples:
- `storage` means assessment artifact storage, not specifically S3 or Blob
- `compute` means hosted processing runtime, not specifically ECS or Container Apps
- `presentation` means static delivery surface, not specifically CloudFront or Static Web Apps

Provider-specific implementations should live under `providers/aws` and `providers/azure`.

---

## Environment Strategy

Each cloud has independent `dev` and `prod` environments.

Environment definitions should:
- compose provider-specific modules
- define region/location choices
- set naming prefixes and tags
- wire secrets and identity inputs
- stay thin and declarative

---

## Expected Evolution

Initial implementation should focus on:
1. ingress
2. storage
3. compute
4. ai
5. presentation

Queue, metadata, identity, and observability should be added immediately after the first deployable platform slice is defined.
