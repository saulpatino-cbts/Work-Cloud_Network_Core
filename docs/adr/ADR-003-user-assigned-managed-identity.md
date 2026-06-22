# ADR-003: User-Assigned Managed Identity for Key Vault and Foundry Access

**Status:** Accepted  
**Date:** 2026-06-22  
**Deciders:** Platform Engineering  

---

## Context

The CNA platform requires managed identities for three access patterns:

| Access pattern | Identity needed |
|---|---|
| Container Apps read Key Vault secret references | Identity with KV Secrets User on the vault |
| Container Apps access Azure Foundry (Cognitive Services) | Identity with Cognitive Services User on the Foundry account |
| Container Apps access Azure Storage | Identity with Storage Blob Data Contributor on the storage account |
| CI validation job accesses Foundry for post-deploy verification | Identity with Cognitive Services User on the Foundry account |

The original platform design used **system-assigned managed identities** exclusively — one per Container App (`cna-web`, `cna-api`, `cna-worker`). Each app received individual RBAC assignments in `dev/main.tf`.

### Problems with the all-system-assigned approach

**1. System-assigned identities are tied to the resource lifecycle.**

A system-assigned identity is created when the Container App is created and deleted when it is deleted. If a Container App is recreated (new Terraform environment, teardown/redeploy), the old RBAC assignments are orphaned and must be re-applied.

**2. Cannot be shared with ephemeral Container Apps Jobs.**

The validation job (`job-validate-foundry-<run_id>`) is created and deleted per CI run. It needs `Cognitive Services User` access to the Foundry account to acquire an OAuth token via `DefaultAzureCredential`. A system-assigned identity for an ephemeral job would require:
- Create job → Azure assigns system identity → wait for propagation → grant RBAC → run job → delete job → RBAC assignment becomes orphaned
- Propagation delay for RBAC makes this unreliable in a CI loop

**3. Key Vault secret references require an identity attached to the Container App.**

The `key_vault_secret_id` field in a Container App secret block requires an `identity` field specifying which managed identity the app uses to read the KV secret. System-assigned identities work, but it means the KV RBAC assignment is per-app (three separate `Key Vault Secrets User` assignments) rather than one assignment for a shared identity.

---

## Decision

**Use the platform's user-assigned managed identity (UAI) for Key Vault secret references and Foundry validation.**

The UAI (`${name_prefix}-id`) was already created in `identity/main.tf` and already holds `Key Vault Secrets Officer` on the vault (assigned in `security/main.tf`). This decision extends its use to:

1. **KV secret references in Container Apps** — all three apps (`cna-web`, `cna-api`, `cna-worker`) now attach the UAI via `identity { type = "SystemAssigned, UserAssigned"; identity_ids = [uai_id] }`. The `key_vault_secret_id` secret blocks reference the UAI for KV reads.

2. **Foundry validation job** — the per-run job (`job-validate-foundry-<run_id>`) attaches the UAI via `--identity $UAI_ID`. The `AZURE_CLIENT_ID` environment variable is set to the UAI's client ID so `DefaultAzureCredential` selects it unambiguously.

3. **Foundry RBAC for the UAI** — a new `azurerm_role_assignment.uai_foundry_user` grants `Cognitive Services User` to `module.identity.managed_identity_principal_id` on `module.ai.foundry_account_id`. This is in addition to the per-app system-assigned identity assignments that remain for the live Container Apps.

The three Container Apps retain their system-assigned identities for Storage Blob Data Contributor (already assigned to their system-assigned principal IDs in `dev/main.tf`). The identity type is `SystemAssigned, UserAssigned` — both are active simultaneously.

---

## Rationale

### Microsoft documentation alignment

Microsoft recommends user-assigned managed identities for workloads that share credentials or are recreated frequently:

> Use a user-assigned managed identity when you need to share a single identity between multiple resources, when resources need an identity during provisioning, or when resources are recycled frequently but permissions need to stay consistent.  
> — *[Managed identity best practices](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)*

For Container Apps Jobs specifically, the docs show the UAI pattern as the standard for jobs that need Azure resource access:

> Assign a user-assigned managed identity to a job to grant it access to Azure resources without managing credentials.  
> — *[Managed identities in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity)*

The `DefaultAzureCredential` in the Azure SDK respects the `AZURE_CLIENT_ID` environment variable to select a specific user-assigned identity, which avoids ambiguity when multiple identities are attached:

> Set the `AZURE_CLIENT_ID` environment variable to the client ID of a user-assigned managed identity to use that identity when using `DefaultAzureCredential`.  
> — *[Azure Identity client library for JavaScript](https://learn.microsoft.com/en-us/javascript/api/overview/azure/identity-readme)*

### Why the combined identity type `SystemAssigned, UserAssigned` is correct

The existing Storage RBAC assignments target the system-assigned principal IDs of each Container App. Changing to `UserAssigned` only would break those assignments. Using `SystemAssigned, UserAssigned` preserves the system identity for storage access while adding the UAI for KV and Foundry access.

This is the Microsoft-recommended pattern when an app needs both:

> You can enable both system-assigned and user-assigned managed identities on the same app simultaneously.  
> — *[Use managed identities for App Service and Azure Functions](https://learn.microsoft.com/en-us/azure/app-service/overview-managed-identity)*

### Single RBAC assignment for KV access

With the UAI, a single `Key Vault Secrets Officer` assignment (already present in `security/main.tf`) covers:
- All three Container Apps reading KV secret references
- The validation job reading Cognitive Services tokens (via the UAI, not KV, but same identity)

Without the UAI, we would need three separate `Key Vault Secrets User` assignments (one per Container App system identity) plus handling the ephemeral job identity problem separately.

---

## Consequences

**Positive:**
- Single identity for KV access — three fewer RBAC assignments to manage
- Validation job reuses an established, permanently assigned identity — no propagation delay
- Identity persists across Container App teardown/recreate — no orphaned RBAC assignments
- `DefaultAzureCredential` works correctly in the validation job via `AZURE_CLIENT_ID` env var

**Negative / trade-offs:**
- Container Apps now carry two identity attachments (`SystemAssigned, UserAssigned`) — slightly more complex identity configuration to reason about
- The UAI must always be provisioned before the Container Apps in a fresh environment (Terraform dependency graph handles this since `module.compute` depends on `module.identity`)
- The `Cognitive Services User` role for the UAI is an additive grant — if Foundry RBAC is ever locked down, the UAI also needs to be included in the allowlist

**Neutral:**
- The `azurerm_role_assignment.uai_foundry_user` resource is idempotent — duplicate grants for the same principal/role/scope are rejected by Azure and Terraform tracks them correctly

---

## Alternatives Considered

### A: Grant Cognitive Services User to the system-assigned identity of a dedicated persistent job Container App
Rejected. A "persistent" Container Apps Job would idle at zero cost but still requires an identity and RBAC assignment tied to that resource. It adds a resource that exists only for CI tooling, which is harder to justify and creates an orphaned identity if the environment is torn down.

### B: Use system-assigned identity for each Container App plus federated credentials for the job
Rejected. Federated credentials (GitHub Actions OIDC) are appropriate for the CI runner itself, not for in-VNet tasks. The job needs network-attached Azure credentials, which managed identity provides natively.

### C: Use the CI service principal (AZURE_CLIENT_ID / OIDC) to run in-VNet tasks
Rejected. The CI service principal is a federated identity bound to the GitHub Actions runner, which runs outside the VNet. It cannot be used as a managed identity inside the Container App environment.

---

## Related Decisions

- [ADR-001](ADR-001-container-apps-job-for-deployment-tasks.md) — Container Apps Jobs for deployment tasks
- [ADR-002](ADR-002-key-vault-references-for-container-app-secrets.md) — Key Vault references for Container App secrets
