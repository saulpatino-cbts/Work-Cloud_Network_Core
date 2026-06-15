# Network Security Implementation Plan

## Objective

Implement the approved Azure networking security target state for CNA:

- Azure Front Door Premium remains the global edge
- Azure Firewall is introduced for centralized egress inspection and control
- subnet-specific NSGs enforce east-west least privilege
- shared Log Analytics becomes the central infrastructure and security evidence
  plane
- Azure PaaS dependencies remain private wherever supported

## Approved target state

1. Front Door Premium stays as the public entry point.
2. Application Gateway remains optional unless needed for stronger regional
   origin protection.
3. Azure Firewall becomes mandatory for routed outbound control.
4. Each subnet gets its own NSG with explicit policy intent.
5. All diagnostics go to the same Log Analytics workspace.
6. Application Insights remains in use for app telemetry.
7. Key Vault, Storage, and PostgreSQL stay private; future PaaS services should
   follow the same model where supported.

## Phase 1: Edge and ingress hardening

1. Confirm the final origin protection pattern behind Front Door.
2. Eliminate direct-origin bypass for the web tier.
3. Preserve Front Door WAF and health checks during the hardening change.

Deliverables:

- origin protection Terraform design
- updated ingress path
- validation checklist for sign-in, health probes, and WAF behavior

## Phase 2: East-west segmentation

1. Split the current shared NSG into subnet-specific NSGs.
2. Define explicit subnet intents for:
   - app/runtime subnet
   - private endpoint subnet
   - database subnet
3. Add only the minimum required rules for workload and platform function.

Deliverables:

- new NSG resources
- subnet association updates
- rule matrix documenting allowed flows

## Phase 3: North-south egress control

1. Introduce Azure Firewall.
2. Create route tables and UDRs for workload subnets.
3. Route outbound internet-bound traffic through Firewall.
4. Define initial application and network rule collections.

Deliverables:

- Azure Firewall module design
- route tables and subnet associations
- outbound allowlist baseline

## Phase 4: Centralized logging and evidence

1. Reuse the existing Log Analytics workspace as the shared evidence plane.
2. Add diagnostic settings for:
   - Front Door
   - Front Door WAF
   - Azure Firewall
   - NSG flow logs
   - Container Apps
   - Key Vault
   - Storage
   - PostgreSQL
3. Keep Application Insights for app telemetry.

Deliverables:

- diagnostic settings across all major resources
- retention guidance by log class
- query pack for deployment validation

## Phase 5: Private PaaS consistency

1. Validate current private endpoint and delegated private access paths.
2. Ensure private DNS zones are consistently linked and documented.
3. Identify any remaining public PaaS dependencies and classify them as either:
   - removable
   - temporary exception
   - accepted long-term dependency

Deliverables:

- private service inventory
- DNS and endpoint validation checklist
- exception register for public dependencies

## Phase 6: AI Foundry exception review

1. Review the selected Foundry feature set for private networking support.
2. If support exists, plan a move toward private access.
3. If not, document public Foundry access as an explicit architecture
   exception.

Deliverables:

- Foundry networking decision note
- risk acceptance or privatization backlog item

## Validation gates

1. Public traffic reaches the application only through the approved edge path.
2. Subnet policy proves least privilege east-west access.
3. Outbound internet access is visible and controlled through Firewall.
4. Log Analytics receives diagnostics from all major network and security
   resources.
5. Application Insights continues capturing app traces successfully.
6. Private PaaS name resolution works without fallback to public endpoints.

## Recommended implementation order

1. Logging foundation
2. NSG split and subnet policy
3. Azure Firewall and UDRs
4. Edge/origin hardening
5. Private PaaS validation
6. AI Foundry exception resolution
