# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/providers/azure/database/ in shape (same five
# files, same name_prefix/tags contract) but intentionally holds no AWS
# resources: engine TBD (default direction: RDS for PostgreSQL, matching Azure's Postgres Flexible Server 1:1 so the existing Prisma schema needs no changes).
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
# (AWS Terraform provider modules) -- service selection for this module is a
# per-module follow-up issue, not decided here.

# Resource blocks land here once the module's service is confirmed.
