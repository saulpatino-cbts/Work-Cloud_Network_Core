# ADR-002: Key Vault References for Container App Secrets

**Status:** Accepted  
**Date:** 2026-06-22  
**Deciders:** Platform Engineering  

---

## Context

The CNA platform stores four sensitive values that Container Apps need at runtime:

| Secret name | Purpose |
|---|---|
| `database-url` | PostgreSQL connection string (computed by Terraform from server FQDN + urlencoded admin password) |
| `nextauth-secret` | Auth.js v5 JWT signing key |
| `entra-client-secret` | Entra ID (Azure AD) OAuth2 client secret for NextAuth |
| `credential-encryption-key` | AES-256 key for encrypting stored cloud credentials |

### Original approach: raw values in Container App secrets

The original design passed secret values directly into the Container App's secret store:

```hcl
container_app_secrets = {
  "database-url"        = module.database.connection_string
  "nextauth-secret"     = var.nextauth_secret
  "entra-client-secret" = var.entra_client_secret
  "credential-encryption-key" = var.credential_encryption_key
}
```

These values were stored encrypted within the Container App resource itself, injected into container environment variables via `secretref:`.

### Problems with raw value secrets

**1. Secrets are revision-scoped, not live-updated.**

Azure Container Apps documents this behavior explicitly:

> Changing a secret value does **not** automatically restart the revision. When you update a secret's value, the revision continues using the old value until it is restarted or a new revision is created.  
> — *[Manage secrets in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)*

This caused a `CrashLoopBackOff` after the `urlencode()` fix to `database/outputs.tf`. The connection string format changed (special characters percent-encoded), but the running revision still held the old raw-format value. The crash loop persisted until the revision was manually restarted — which required adding a CI step to detect and restart stale revisions on every deploy.

**2. Secret values are opaque to Azure Key Vault.**

With raw values, there is no rotation policy, no expiry notification, no audit log of access, and no version history in Key Vault. The secrets exist only inside the Container App resource. If the Container App is deleted and recreated, the secrets must be re-injected.

**3. `ignore_changes` workaround masked a real bug.**

The `runtime/main.tf` KV secrets had `lifecycle { ignore_changes = [value] }` to prevent Terraform from overwriting rotated values. This caused the corrected (urlencoded) `database-url` value to never flow into Key Vault — the KV secret held the old format while the Container App received a fresh copy from `module.database.connection_string`. The two were out of sync.

---

## Decision

**Store all Container App secrets in Azure Key Vault and reference them via versionless URIs.**

```hcl
container_app_kv_secrets = {
  "database-url"              = "${module.identity.key_vault_uri}secrets/cna-database-url"
  "nextauth-secret"           = "${module.identity.key_vault_uri}secrets/cna-nextauth-secret"
  "entra-client-secret"       = "${module.identity.key_vault_uri}secrets/cna-entra-client-secret"
  "credential-encryption-key" = "${module.identity.key_vault_uri}secrets/cna-credential-encryption-key"
}
```

Each Container App secret block now uses `key_vault_secret_id` instead of `value`:

```hcl
secret {
  name                = "database-url"
  key_vault_secret_id = "https://vault.vault.azure.net/secrets/cna-database-url"
  identity            = var.key_vault_reference_identity_id  # user-assigned managed identity
}
```

---

## Rationale

### Microsoft documentation alignment

Microsoft Learn names Key Vault references as the recommended pattern for sensitive values in Container Apps:

> We recommend using Azure Key Vault to store your application's secrets. You can reference secrets stored in an Azure key vault using a Key Vault secret URI in your container app.  
> — *[Use Key Vault references in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets#reference-secret-from-key-vault)*

For the versionless URI pattern (no version segment in the URI):

> When you use a versionless secret URI, Azure Container Apps automatically uses the latest version of the secret. When a newer version is available, the container app automatically updates to use the new version within 30 minutes.  
> — *[Manage secrets in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)*

The 30-minute auto-refresh window means secret rotation no longer requires a Terraform apply or manual CI step. For same-run pickup, a single `az containerapp revision restart` is sufficient.

### How this eliminates the stale-secret crash loop

With KV references:
1. Terraform updates `cna-database-url` in Key Vault with the current (urlencoded) connection string.
2. The Container App reads the value from Key Vault when the revision starts — it always gets the current value.
3. The `ignore_changes` workaround is no longer needed on `cna-database-url` because Terraform managing the KV secret value is the desired behavior (it is computed infrastructure output, not a manually rotated credential).

### Rotation without Terraform

`nextauth-secret`, `entra-client-secret`, and `credential-encryption-key` retain `lifecycle { ignore_changes = [value] }` in the Key Vault secret resource. This allows them to be rotated directly in Key Vault (portal, CLI, or rotation policy) without requiring a Terraform apply. The Container App picks up the new version within 30 minutes automatically via the versionless reference.

`cna-database-url` does **not** have `ignore_changes` because it is a computed value derived from live infrastructure (`module.database.connection_string`). It must always match what Terraform knows the database server exposes.

### Single source of truth

Key Vault becomes the authoritative store for all platform secrets. The same Key Vault is already used by the `05-sync-env` workflow. Both consumers now reference the same source:

```
Terraform apply
  → module.runtime creates/updates KV secrets
  → module.compute Container Apps reference KV secrets via versionless URI
  → Container App always has current value at revision start
```

### Dependency ordering

An explicit `depends_on = [module.runtime]` is added to `module.compute` in both `dev/main.tf` and `prod/main.tf`. This ensures Key Vault secrets exist before the Container App references them — particularly important for fresh environment provisioning where both are created in the same apply.

---

## Consequences

**Positive:**
- No more stale-secret CrashLoopBackOff — Container Apps always read current values from KV
- Automatic rotation pickup (within 30 min) without Terraform or CI involvement
- Full audit log of every secret access in Key Vault diagnostic logs
- Secret values are never stored in Terraform state or Container App resource definition
- `cna-credential-encryption-key` is now properly stored in Key Vault (previously it only existed as a raw Container App secret with no KV copy)

**Negative / trade-offs:**
- Container Apps require outbound HTTPS access to Key Vault to read secret references; this is already allowed by the Azure Firewall FQDN allowlist
- The user-assigned managed identity must have at minimum `Key Vault Secrets User` on the vault; the existing `Key Vault Secrets Officer` assignment covers this
- First apply after migration rolls a new revision on all three apps (expected one-time change as secrets move from `value` to `key_vault_secret_id`)

---

## Alternatives Considered

### A: Keep raw values, fix the stale-secret problem with revision restart in CI
Rejected. Revision restart in CI works but requires the CI job to know when secrets have changed. With KV references, Azure handles this automatically. Raw values also provide no rotation path without Terraform.

### B: Use Azure App Configuration with Key Vault references
Over-engineered for this use case. App Configuration is appropriate for dynamic feature flags and non-sensitive configuration. Secrets belong in Key Vault directly.

### C: Inject secrets as plain environment variables (no secretref)
Rejected on security grounds. Plain environment variables appear in plaintext in Container Apps revision definitions, which are visible to anyone with Reader access to the Container App resource. Secrets must be stored as Container App secrets or KV references.

---

## Related Decisions

- [ADR-001](ADR-001-container-apps-job-for-deployment-tasks.md) — Container Apps Jobs for deployment tasks
- [ADR-003](ADR-003-user-assigned-managed-identity.md) — User-assigned managed identity for KV and Foundry access
