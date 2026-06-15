# ADF-009: Private Endpoint Approval Automation For Front Door Origins

## Status

Accepted

## Context

Azure Front Door Private Link does not pass traffic until the origin owner
approves the pending private endpoint connection. Microsoft documents that
Azure Front Door creates a private endpoint request and that the request must
be approved before traffic can flow. The Azure Container Apps integration guide
for Front Door shows this as an explicit step after origin creation.

For CNA, a manual approval step is operationally weak:

- it breaks the goal of end-to-end deployment automation
- it creates a hidden dependency during customer go-live or redeploy
- it introduces review risk because ingress appears deployed before it is
  actually usable

## Architecture

Recommended automation pattern:

```text
GitHub Actions workflow
  -> OIDC login to Azure
Deployment identity
  -> create/update Front Door origin with Private Link
  -> poll managed environment privateEndpointConnections
  -> approve matching pending connection
Azure Front Door
  -> private endpoint established
Azure Container Apps managed environment
  -> approved provider-side connection
```

## Decision

Automate the provider-side approval step in the deployment pipeline as a
separate post-provision action, not as an operator-held manual gate.

Preferred implementation:

1. Use the existing deployment workflow with Azure federated identity / OIDC.
2. Grant the deployment identity least-privilege access on:
   - the Front Door profile and origin resources it creates
   - the Container Apps managed environment resource that owns the pending
     private endpoint connection
3. After Front Door origin creation, run a scripted approval step that:
   - lists `Microsoft.App/managedEnvironments` private endpoint connections
   - filters the pending connection by request description and/or target origin
   - approves the pending request
   - waits until the connection reports approved and usable
4. Log the approved connection ID and state as deployment evidence.

## Flow

1. Workflow authenticates to Azure using workload identity federation.
2. Terraform provisions the Front Door profile/origin and Container Apps
   managed environment settings.
3. Front Door submits a private endpoint connection request.
4. Pipeline polls the managed environment for pending connection requests.
5. Pipeline approves the matching request.
6. Pipeline waits for the approved state and only then continues to validation.

## Why this decision

- Microsoft explicitly documents the approval as part of the setup flow.
- A deployment that stops at "pending private endpoint" is not actually
  complete.
- Approval logic is procedural and eventual-consistency-sensitive, which makes
  it a better fit for pipeline orchestration than a pure Terraform resource
  graph.

## Consequences

Positive:

- Makes the ingress hardening path deployable without operator intervention.
- Produces an auditable and repeatable approval record.
- Keeps customer demos and tests from failing on a hidden pending connection.

Tradeoffs:

- Requires Azure CLI or PowerShell automation in the deployment workflow.
- Needs careful filtering because Microsoft documents that Front Door may
  create multiple connection requests for the same origin.
- Requires least-privilege review for the approval identity.

## Best-practice recommendation

Best recommendation for CNA:

1. Keep the approval in the GitHub Actions deployment workflow rather than
   embedding it in Terraform.
2. Use Azure OIDC federation for the workflow identity instead of long-lived
   credentials.
3. Scope permissions to the CNA resource group or, preferably, to the specific
   Front Door profile and Container Apps managed environment resources.
4. Prefer a custom role if built-in roles are broader than needed.

Inference from Microsoft guidance:

- The provider-side approval operation requires read and state-change access on
  the managed environment private endpoint connection resource. A least-
  privilege custom role should therefore cover the relevant
  `Microsoft.App/managedEnvironments/privateEndpointConnections/*` operations
  plus read access on the parent managed environment.

## Implementation notes

- Use `az network private-endpoint-connection list --type Microsoft.App/managedEnvironments`
  to discover the pending request.
- Use `az network private-endpoint-connection approve --id <connection-id>` to
  approve it.
- Filter on the request description and connection state to avoid approving an
  unrelated request.
- Treat timeout waiting for a pending request or approved state as a deployment
  failure.

## Microsoft guidance

- Access an Azure container app using an Azure Front Door with Private Link:
  https://learn.microsoft.com/en-us/azure/container-apps/how-to-integrate-with-azure-front-door
- Secure your origin with Private Link in Azure Front Door Premium:
  https://learn.microsoft.com/en-us/azure/frontdoor/private-link
- Manage Azure private endpoints:
  https://learn.microsoft.com/en-us/azure/private-link/manage-private-endpoint
