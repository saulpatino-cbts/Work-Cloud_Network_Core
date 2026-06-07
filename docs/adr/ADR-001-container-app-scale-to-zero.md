# ADR-001: Scale-to-Zero for Non-Production Container Apps

**Status:** Accepted  
**Date:** 2026-06-07  
**Deciders:** Platform Engineering  
**Tags:** FinOps, compute, Azure Container Apps

---

## Context

The CNA platform runs three Azure Container Apps (API, Worker, Web) in a dev environment that is used intermittently — primarily during active development sprints and CI/CD pipeline runs. The dev environment was previously configured with `min_replicas = 1` on all three apps, meaning at least one instance of each app was running 24/7 regardless of traffic.

Azure Container Apps bills per vCPU-second and per GiB-second of memory consumed. At `min_replicas = 1`, the platform incurs baseline compute charges continuously, even during nights, weekends, and sprint pauses. For a small platform with modest instance sizes, this adds measurable cost without corresponding value.

## Decision

Enable scale-to-zero (`min_replicas = 0`) for all Container Apps in the **dev environment only**.

This is controlled via a new Terraform module variable `enable_scale_to_zero` (default `false`) in `infra/terraform/providers/azure/compute`. The dev environment sets this to `true`; production keeps it at `false`.

```hcl
# compute/main.tf
min_replicas = var.enable_scale_to_zero ? 0 : var.container_app_min_replicas
```

The production environment retains `min_replicas = 1` (or higher per app) to ensure SLA-aligned availability. Scale-to-zero is not appropriate for production because cold-start latency would be user-visible.

## Consequences

**Positive:**
- Dev environment incurs zero compute cost when idle — nights, weekends, and between sprints produce no bill
- No architecture or application changes required — Container Apps handles cold-start internally
- Pattern is parameterized and reversible per environment via a single Terraform variable

**Negative / Risks:**
- First request after an idle period triggers a cold start — typically 2–10 seconds depending on image size. This is acceptable for dev but would be unacceptable in production.
- The Worker app handles async background jobs. If a job is triggered while the worker is scaled to zero, it will cold-start before processing — acceptable latency for dev workloads.
- Health checks in CI pipelines must account for cold-start time or include a warm-up step before running assertions.

**Neutral:**
- The `worker` app previously had a hardcoded `min_replicas = 1` that bypassed the module variable. This was corrected so all three apps respect the same `enable_scale_to_zero` control.
