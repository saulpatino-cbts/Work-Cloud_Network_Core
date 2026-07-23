# SCAFFOLD -- foundation only, no resources declared yet.
#
# Mirrors infra/terraform/environments/azure/prod/platform/main.tf: networking
# is authored directly here, per environment, NOT as a reusable provider
# module -- the Azure side has no providers/azure/network/ module either,
# because VPC/subnet layout is genuinely environment-specific (dev vs prod
# CIDR ranges, HA posture) rather than a reusable building block like compute
# or database.
#
# What belongs here once AWS networking is scoped (mirrors the Azure platform
# env's actual resources: VNet, three purpose-built subnets, NSGs, a firewall
# for egress, route tables, and a platform-owned Log Analytics-equivalent
# workspace for flow logs):
#   - aws_vpc
#   - aws_subnet (compute, database, private-link/endpoints -- same three-subnet
#     split as azurerm_subnet.container_apps_infra / .database / .private_endpoints)
#   - aws_security_group + aws_security_group_rule (NSG equivalent)
#   - aws_nat_gateway or AWS Network Firewall (egress control equivalent to
#     Azure Firewall -- Azure uses a paid firewall for egress allow-listing;
#     decide NAT Gateway vs Network Firewall per issue #110's network follow-up)
#   - aws_route_table + aws_route
#   - aws_cloudwatch_log_group + VPC Flow Logs (equivalent to the platform env's
#     dedicated flow-log storage account + Log Analytics workspace)
#
# Then wires the observability provider module exactly as the Azure platform
# env does, once that module has real resources:
#   module "observability" {
#     source = "../../../../providers/aws/observability"
#     ...
#   }
#
# Tracked in https://github.com/saulpatinojr/Work-Cloud_Network_Assessment/issues/110
