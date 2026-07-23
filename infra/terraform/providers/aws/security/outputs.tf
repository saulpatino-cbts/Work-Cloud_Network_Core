# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/security/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: edge + private-connectivity TBD (default direction: CloudFront + WAF for Front Door's role, VPC endpoints for Private Link's role -- this module is edge protection and private networking, not host-level hardening, matching the Azure security module's actual scope).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Outputs land here once main.tf declares resources to reference.
