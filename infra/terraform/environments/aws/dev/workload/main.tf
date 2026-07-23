# SCAFFOLD -- foundation only, no module blocks wired yet.
#
# Mirrors infra/terraform/environments/azure/dev/workload/main.tf, which
# wires all eight provider modules together: storage, identity, compute, ai,
# runtime, security, observability, database (in that dependency order).
#
# Uncomment and complete each module block as its provider module
# (../../../../providers/aws/<name>) gets real resources. Keep the same
# dependency order the Azure workload does -- identity before compute (roles
# must exist before the service that assumes them), database before runtime
# (runtime writes DATABASE_URL after the instance exists).
#
# module "storage" {
#   source      = "../../../../providers/aws/storage"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# module "identity" {
#   source      = "../../../../providers/aws/identity"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# module "compute" {
#   source      = "../../../../providers/aws/compute"
#   name_prefix = local.name_prefix
#   tags        = local.tags
#   api_image    = var.api_image
#   worker_image = var.worker_image
#   web_image    = var.web_image
# }
#
# module "ai" {
#   source      = "../../../../providers/aws/ai"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# module "runtime" {
#   source      = "../../../../providers/aws/runtime"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# module "security" {
#   source      = "../../../../providers/aws/security"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# module "observability" {
#   source      = "../../../../providers/aws/observability"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# module "database" {
#   source      = "../../../../providers/aws/database"
#   name_prefix = local.name_prefix
#   tags        = local.tags
# }
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
