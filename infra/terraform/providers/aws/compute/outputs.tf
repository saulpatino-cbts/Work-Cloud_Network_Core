# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/compute/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: compute platform TBD (default direction: ECS on Fargate, matching Azure Container Apps' managed-container model -- see the layout discussion in issue #110).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Outputs land here once main.tf declares resources to reference.
