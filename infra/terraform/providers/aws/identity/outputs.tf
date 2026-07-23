# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/identity/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: AWS analog TBD (default direction: Secrets Manager for Key Vault's role, IAM roles/policies for managed identity -- see Development-Provider-Selection-Notes.md).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Outputs land here once main.tf declares resources to reference.
