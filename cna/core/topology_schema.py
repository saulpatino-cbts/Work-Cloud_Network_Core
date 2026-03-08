"""Topology data contracts — bridge between discovery (Phase C) and diagram engine (Phase B).

Version 1.1.0 — Phase B Gap 8 closure.
  Added AWS: SecurityGroup, NACL, VpnGateway, NetworkFirewallPolicy
  Added Azure: AzureFirewall, ApplicationGateway, PrivateDnsZone, ExpressRouteCircuit
  All new fields are Optional with default_factory so v1.0.0 data remains valid.
"""
from __future__ import annotations

from enum import Enum, StrEnum

from pydantic import BaseModel, Field

TOPOLOGY_SCHEMA_VERSION = "1.1.0"


# ── Enums ──────────────────────────────────────────────────────────────────

class SubnetType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    ISOLATED = "isolated"
    UNKNOWN = "unknown"


class AttachmentType(StrEnum):
    VPC = "vpc"
    VPN = "vpn"
    DIRECT_CONNECT = "direct_connect"
    PEERING = "peering"
    CONNECT = "connect"


class PeeringState(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DELETED = "deleted"


# ── AWS primitives ─────────────────────────────────────────────────────────

class RouteEntry(BaseModel):
    destination: str
    target: str
    target_type: str
    state: str = "active"


class RouteTable(BaseModel):
    id: str
    name: str | None = None
    associated_subnet_ids: list[str] = Field(default_factory=list)
    routes: list[RouteEntry] = Field(default_factory=list)
    is_main: bool = False


class SecurityGroupRule(BaseModel):
    rule_id: str | None = None
    direction: str                  # "ingress" | "egress"
    protocol: str                   # tcp | udp | icmp | -1 (all)
    from_port: int | None = None
    to_port: int | None = None
    cidr_ranges: list[str] = Field(default_factory=list)
    source_sg_id: str | None = None
    description: str | None = None


class SecurityGroup(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    vpc_id: str
    rules: list[SecurityGroupRule] = Field(default_factory=list)
    tags: dict = Field(default_factory=dict)


class NACLEntry(BaseModel):
    rule_number: int
    protocol: str
    rule_action: str    # "allow" | "deny"
    cidr: str
    from_port: int | None = None
    to_port: int | None = None
    egress: bool


class NACL(BaseModel):
    id: str
    name: str | None = None
    vpc_id: str
    is_default: bool = False
    entries: list[NACLEntry] = Field(default_factory=list)
    associated_subnet_ids: list[str] = Field(default_factory=list)


class VpnGateway(BaseModel):
    id: str
    name: str | None = None
    state: str
    type: str = "ipsec.1"
    amazon_side_asn: Optional[int] = None
    vpc_id: Optional[str] = None


class NetworkFirewallPolicy(BaseModel):
    arn: str
    name: str
    vpc_id: str
    firewall_subnet_ids: list[str] = Field(default_factory=list)
    stateful_rule_group_arns: list[str] = Field(default_factory=list)
    stateless_rule_group_arns: list[str] = Field(default_factory=list)


class Subnet(BaseModel):
    id: str
    name: str | None = None
    cidr: str
    az: str
    subnet_type: SubnetType = SubnetType.UNKNOWN
    route_table_id: Optional[str] = None
    nacl_id: Optional[str] = None
    auto_assign_public_ip: bool = False


class InternetGateway(BaseModel):
    id: str
    name: str | None = None
    state: str = "attached"


class NatGateway(BaseModel):
    id: str
    name: str | None = None
    subnet_id: str
    state: str
    public_ip: Optional[str] = None


class VpcPeeringConnection(BaseModel):
    id: str
    name: str | None = None
    requester_vpc_id: str
    requester_account_id: str
    requester_region: str
    accepter_vpc_id: str
    accepter_account_id: str
    accepter_region: str
    state: PeeringState


class VPC(BaseModel):
    id: str
    name: str | None = None
    cidr: str
    secondary_cidrs: list[str] = Field(default_factory=list)
    is_default: bool = False
    subnets: list[Subnet] = Field(default_factory=list)
    route_tables: list[RouteTable] = Field(default_factory=list)
    internet_gateways: list[InternetGateway] = Field(default_factory=list)
    nat_gateways: list[NatGateway] = Field(default_factory=list)
    peering_connections: list[VpcPeeringConnection] = Field(default_factory=list)
    security_groups: list[SecurityGroup] = Field(default_factory=list)
    nacls: list[NACL] = Field(default_factory=list)
    flow_logs_enabled: bool = False
    tags: dict = Field(default_factory=dict)


class TGWAttachment(BaseModel):
    id: str
    resource_id: str
    resource_type: AttachmentType
    resource_owner_account_id: str
    state: str
    association_route_table_id: Optional[str] = None


class TransitGateway(BaseModel):
    id: str
    name: str | None = None
    owner_account_id: str
    amazon_side_asn: Optional[int] = None
    attachments: list[TGWAttachment] = Field(default_factory=list)
    route_table_ids: list[str] = Field(default_factory=list)
    dns_support: bool = True
    vpn_ecmp_support: bool = True
    default_route_table_association: bool = True
    default_route_table_propagation: bool = True


class DirectConnectConnection(BaseModel):
    id: str
    name: str | None = None
    location: str
    bandwidth: str
    state: str
    owner_account_id: str


class AWSAccount(BaseModel):
    account_id: str
    account_name: Optional[str] = None
    ou_id: Optional[str] = None
    ou_name: Optional[str] = None
    is_management_account: bool = False


class AWSRegionTopology(BaseModel):
    account_id: str
    region: str
    vpcs: list[VPC] = Field(default_factory=list)
    transit_gateways: list[TransitGateway] = Field(default_factory=list)
    direct_connect_connections: list[DirectConnectConnection] = Field(default_factory=list)
    vpn_gateways: list[VpnGateway] = Field(default_factory=list)
    network_firewalls: list[NetworkFirewallPolicy] = Field(default_factory=list)
    discovery_blocked: bool = False
    block_reason: Optional[str] = None


class AWSTopology(BaseModel):
    schema_version: str = TOPOLOGY_SCHEMA_VERSION
    engagement_id: str
    accounts: list[AWSAccount] = Field(default_factory=list)
    regions: list[AWSRegionTopology] = Field(default_factory=list)
    management_account_id: Optional[str] = None
    organization_id: Optional[str] = None


# ── Azure primitives ───────────────────────────────────────────────────────

class AzureSubnet(BaseModel):
    id: str
    name: str
    address_prefix: str
    nsg_id: Optional[str] = None
    route_table_id: Optional[str] = None
    service_endpoints: list[str] = Field(default_factory=list)
    private_endpoint_network_policies: str = "Enabled"
    delegation: Optional[str] = None


class AzureRouteEntry(BaseModel):
    name: str
    address_prefix: str
    next_hop_type: str
    next_hop_ip: Optional[str] = None


class AzureRouteTable(BaseModel):
    id: str
    name: str
    location: str
    routes: list[AzureRouteEntry] = Field(default_factory=list)
    associated_subnet_ids: list[str] = Field(default_factory=list)
    disable_bgp_route_propagation: bool = False


class VNetPeering(BaseModel):
    id: str
    name: str
    remote_vnet_id: str
    remote_vnet_name: Optional[str] = None
    remote_subscription_id: str
    peering_state: str
    allow_forwarded_traffic: bool
    allow_gateway_transit: bool
    use_remote_gateways: bool


class AzureFirewall(BaseModel):
    id: str
    name: str
    location: str
    resource_group: str
    sku_tier: str                   # "Basic" | "Standard" | "Premium"
    subnet_id: Optional[str] = None # AzureFirewallSubnet
    public_ip_ids: list[str] = Field(default_factory=list)
    policy_id: Optional[str] = None
    threat_intel_mode: str = "Alert"


class ApplicationGateway(BaseModel):
    id: str
    name: str
    location: str
    resource_group: str
    sku_name: str                   # "Standard_v2" | "WAF_v2"
    subnet_id: str
    waf_enabled: bool = False
    frontend_ip_configs: list[str] = Field(default_factory=list)


class PrivateDnsZone(BaseModel):
    id: str
    name: str                       # e.g. "privatelink.blob.core.windows.net"
    resource_group: str
    linked_vnet_ids: list[str] = Field(default_factory=list)
    record_count: int = 0


class ExpressRouteCircuit(BaseModel):
    id: str
    name: str
    location: str
    resource_group: str
    service_provider: Optional[str] = None
    peering_location: Optional[str] = None
    bandwidth_mbps: Optional[int] = None
    sku_tier: str = "Standard"      # "Standard" | "Premium"
    sku_family: str = "MeteredData" # "MeteredData" | "UnlimitedData"
    circuit_provisioning_state: str = "Enabled"


class VNet(BaseModel):
    id: str
    name: str
    location: str
    resource_group: str
    subscription_id: str
    address_space: list[str] = Field(default_factory=list)
    subnets: list[AzureSubnet] = Field(default_factory=list)
    route_tables: list[AzureRouteTable] = Field(default_factory=list)
    peerings: list[VNetPeering] = Field(default_factory=list)
    ddos_protection_enabled: bool = False
    tags: dict = Field(default_factory=dict)


class AzureVHub(BaseModel):
    id: str
    name: str
    location: str
    resource_group: str
    address_prefix: str
    sku: str = "Standard"
    connected_vnet_ids: list[str] = Field(default_factory=list)
    connected_vpn_site_ids: list[str] = Field(default_factory=list)
    express_route_gateway_id: Optional[str] = None
    azure_firewall_id: Optional[str] = None
    routing_state: str


class AzureVWan(BaseModel):
    id: str
    name: str
    resource_group: str
    sku: str
    hubs: list[AzureVHub] = Field(default_factory=list)


class ManagementGroup(BaseModel):
    id: str
    name: str
    display_name: str
    parent_id: Optional[str] = None
    subscription_ids: list[str] = Field(default_factory=list)
    child_mg_ids: list[str] = Field(default_factory=list)


class AzureSubscriptionTopology(BaseModel):
    subscription_id: str
    subscription_name: Optional[str] = None
    tenant_id: str
    vnets: list[VNet] = Field(default_factory=list)
    virtual_wans: list[AzureVWan] = Field(default_factory=list)
    firewalls: list[AzureFirewall] = Field(default_factory=list)
    application_gateways: list[ApplicationGateway] = Field(default_factory=list)
    private_dns_zones: list[PrivateDnsZone] = Field(default_factory=list)
    express_route_circuits: list[ExpressRouteCircuit] = Field(default_factory=list)
    discovery_blocked: bool = False
    block_reason: Optional[str] = None


class AzureTopology(BaseModel):
    schema_version: str = TOPOLOGY_SCHEMA_VERSION
    engagement_id: str
    tenant_id: str
    management_groups: list[ManagementGroup] = Field(default_factory=list)
    subscriptions: list[AzureSubscriptionTopology] = Field(default_factory=list)
