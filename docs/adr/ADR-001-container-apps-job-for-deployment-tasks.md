# ADR-001: Use Container Apps Jobs for Deployment-Time Tasks

**Status:** Accepted  
**Date:** 2026-06-22  
**Deciders:** Platform Engineering  

---

## Context

The CNA platform uses Azure Container Apps (ACA) with `enable_scale_to_zero = true` in the dev environment for cost efficiency — apps idle to zero replicas when not in use. Two deployment-time tasks required running code inside the VNet:

1. **Database migrations** — run `prisma migrate deploy` against the PostgreSQL Flexible Server, which is only reachable from within the VNet.
2. **Foundry validation** — verify that the Foundry private endpoint DNS resolves to the correct private subnet and that the managed identity can obtain a Cognitive Services token and perform an inference call.

The original Foundry validation approach used `az containerapp exec` to run a Node.js script inside the live web Container App. This proved fundamentally incompatible with the platform's architecture.

### Root problems with `az containerapp exec`

| Problem | Impact |
|---|---|
| Requires a live replica — cannot wake a scaled-to-zero app | Forced `az containerapp update --min-replicas 1` on every deploy |
| `min-replicas` update creates a new revision | Triggered Terraform revision suffix collisions when deterministic suffixes were used |
| New revision stabilization takes 60–120 seconds | Required polling loops and timed out in ~30% of runs |
| WebSocket proxy returns HTTP 404 while a revision is stabilizing | Added a secondary "exec transport probe" loop, doubling the polling window |
| Restoring `min-replicas=0` after validation introduced drift | Required an `if: always()` cleanup step that could itself fail |
| `exec` session is for interactive debugging only | Not a deployment validation contract — Microsoft does not support or recommend it as a CI gate |

Five separate patch attempts over multiple sessions all failed to make this reliable, each fix introducing a new race condition.

---

## Decision

**Use Azure Container Apps Jobs for all deployment-time tasks** — both the existing database migration and the new Foundry validation.

A Container Apps Job is created ad-hoc by the CI workflow (`az containerapp job create --trigger-type Manual`), started, polled for completion via `az containerapp job execution list`, and deleted after the run. Logs are captured from Log Analytics.

---

## Rationale

### Microsoft documentation alignment

Microsoft Learn explicitly distinguishes Container App types by workload pattern:

> **Container Apps** — long-running HTTP services and background processing apps.  
> **Container Apps Jobs** — finite tasks triggered manually, on a schedule, or by events. Jobs exit with a success or failure code when the task completes.  
> — *[Container Apps Jobs overview](https://learn.microsoft.com/en-us/azure/container-apps/jobs)*

`az containerapp exec` is documented under **Debugging and troubleshooting**, not deployment:

> Use `az containerapp exec` to connect to a running container for debugging purposes.  
> — *[Connect to a container for debugging](https://learn.microsoft.com/en-us/azure/container-apps/container-console)*

Using a debugging tool as a CI gate violates the intended use of the API and creates a dependency on undocumented timeout and WebSocket behavior.

### Why Jobs solve the exec problems

| exec problem | How Jobs solve it |
|---|---|
| Needs warm replica | Jobs provision their own ephemeral replica — scale-to-zero state of other apps is irrelevant |
| min-replicas churn | Not needed; no revision change on the live app |
| Revision stabilization race | No dependency on live app revision state |
| WebSocket fragility | Jobs use ARM polling (`execution.properties.status`) — no WebSocket |
| Restore step drift | No drift introduced — the live app is never touched |

### Consistency with existing patterns

The database migration job already uses this pattern successfully (`job-migrate-<run_id>`). The Foundry validation job is a direct parallel:

```
job-migrate-<run_id>    → runs prisma migrate deploy inside VNet
job-validate-foundry-<run_id> → runs DNS + identity + inference check inside VNet
```

Both are created per-run, use the Container Apps environment for VNet access, exit 0 on success / 1 on failure, and are cleaned up on exit.

### Managed identity for Cognitive Services access

The validation job uses the platform's **user-assigned managed identity** (UAI) rather than a job-scoped system-assigned identity. This is because:

1. The UAI already holds `Key Vault Secrets Officer` on the Key Vault (established in `security/main.tf`).
2. Granting `Cognitive Services User` to the UAI on the Foundry account (`dev/main.tf: uai_foundry_user`) is a single additive RBAC assignment.
3. `DefaultAzureCredential` in the Node.js script automatically uses the UAI when `AZURE_CLIENT_ID` is set in the container environment.

Microsoft recommends user-assigned managed identities over system-assigned for workloads that need a persistent, shareable identity:

> Use a user-assigned managed identity when you need to share credentials between multiple resources, or when resources are recreated frequently.  
> — *[Managed identity best practices](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)*

---

## Consequences

**Positive:**
- No more min-replicas manipulation → no Terraform revision drift
- No more exec WebSocket races → deterministic pass/fail in CI
- Validation runs inside the VNet naturally — same network path as production traffic
- Pattern is idempotent: each run creates a fresh job, runs it, and deletes it

**Negative / trade-offs:**
- Job creation adds ~15–20 seconds to the deploy run (job provisioning, image pull)
- If the web image is large, cold pull inside the environment adds latency on the first run after a new image version (subsequent runs benefit from node-level layer caching)
- Log Analytics ingestion latency (2–5 min) means failure logs may not appear immediately — the `sleep 40` before log query (matching the migration pattern) mitigates this

**Neutral:**
- The cleanup `trap` in the script ensures the job resource is deleted whether the script exits 0 or 1, keeping the resource group clean

---

## Alternatives Considered

### A: Keep exec, fix the WebSocket race with a longer probe loop
Rejected. The WebSocket 404 is not a timing issue that a longer loop solves — it is a platform behavior during revision stabilization. Five patch iterations confirmed this. The probe loop was already at 30 × 10s = 5 minutes.

### B: Use a dedicated validation container image (node:alpine + @azure/identity)
Considered but unnecessary. The web image already has Node.js and `@azure/identity` installed (the web app uses `DefaultAzureCredential` at runtime). Reusing it avoids maintaining a separate image.

### C: Use Azure Functions or Logic Apps for validation
Over-engineered for a CI gate. Container Apps Jobs provide the same capability (ephemeral container inside a VNet) with no additional service dependency.

---

## Related Decisions

- [ADR-002](ADR-002-key-vault-references-for-container-app-secrets.md) — Key Vault references for Container App secrets
- [ADR-003](ADR-003-user-assigned-managed-identity.md) — User-assigned managed identity for KV and Foundry access
