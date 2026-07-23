# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/runtime/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: thin post-creation wiring layer TBD -- mirrors Azure runtime's job of writing secret values and role assignments after identity/compute/database exist (e.g. writing DATABASE_URL into Secrets Manager, wiring the ECS task role to it).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

variable "name_prefix" {
  description = "Normalized name prefix for runtime wiring resources"
  type        = string
}

variable "tags" {
  description = "Tags applied to runtime wiring resources"
  type        = map(string)
  default     = {}
  nullable    = false
}
