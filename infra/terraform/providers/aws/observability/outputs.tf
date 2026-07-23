# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/observability/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: AWS analog TBD (default direction: CloudWatch Logs/Alarms + AWS Distro for OpenTelemetry, matching Azure's Log Analytics + Monitor diagnostic settings).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Outputs land here once main.tf declares resources to reference.
