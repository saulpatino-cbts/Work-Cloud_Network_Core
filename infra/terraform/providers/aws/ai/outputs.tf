# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/ai/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: AWS AI service TBD (default direction: Amazon Bedrock, per the wiki's Provider Selection Notes -- AWS AI = Bedrock).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Outputs land here once main.tf declares resources to reference.
