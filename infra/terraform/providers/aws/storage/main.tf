# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/storage/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: AWS analog TBD (default direction: S3 with static website hosting + lifecycle policies, matching the Azure storage account 1:1 -- same four logical buckets/containers: raw-artifacts, normalized-artifacts, deliverables, static-site).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Resource blocks land here once the module's service is confirmed.
