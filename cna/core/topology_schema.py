"""Topology data contracts — the bridge between discovery (Phase C) and diagram engine (Phase B).

Criticized in TODO_PhaseA.md: diagram engine had no defined input contract.
This file IS that contract. Every diagram generator imports from here.
Every discovery writer outputs to these models.
Version-pinned so schema drift is detected, not silently swallowed.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

TOPOLOGY_SCHEMA_VERSION = "1.0.0"


# ── Enums ──────────────────────────────────────────────────────────────────

class SubnetType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ISOLATED = "isolated"
    UNKNOWN = "unknown"


class AttachmentType(str, Enum):
    VPC = "vpc"
    VPN = "vpn"
    DIRECT_CONNECT = "direct_connect"
    PEERING = "peering"
    CONNECT = "connect"


class PeeringState(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DELETED = "deleted"


# ── AWS primitives ─────────────────────────────────────────────────────────

class RouteEntry(BaseModel):
    destination: str                    # CIDR or prefix list
    target: str                         # igw-xxx | nat-xxx | tgw-xxx | local | etc.
    target_type: str                    # igw | nat | tgw | local | pcx | vpgw | eni
    state: str = "active"


class RouteTable(BaseModel):
    id: str
    name: Optional[str] = None
    associated_subnet_ids: list[str] = Field(default_factory=list)
    routes: list[RouteEntry] = Field(default_factory=list)
    is_main: bool = False


class Subnet(BaseModel):
    id: str
    name: Optional[str] = None
    cidr: str
    az: str
    subnet_type: SubnetType = SubnetType.UNKNOWN
    route_table_id: Optional[str] = None
    nacl_id: Optional[str] = None
    auto_assign_public_ip: bool = False


class InternetGateway(BaseModel):
    id: str
    name: Optional[str] = None
    state: str = "attached"


class NatGateway(BaseModel):
    id: str
    name: Optional[str] = None
    subnet_id: str
    state: str
    public_ip: Optional[str] = None


class VpcPeeringConnection(BaseModel):
    id: str
    name: Optional[str] = None
    requester_vpc_id: str
    requester_account_id: str
    requester_region: str
    accepter_vpc_id: str
    accepter_account_id: str
    accepter_region: str
    state: PeeringState


class VPC(BaseModel):
    id: str
    name: Optional[str] = None
    cidr: str
    secondary_cidrs: list[str] = Field(default_factory=list)
    is_default: bool = False
    subnets: list[Subnet] = Field(default_factory=list)
    route_tables: list[RouteTable] = Field(default_factory=list)
    internet_gateways: list[InternetGateway] = Field(default_factory=list)
    nat_gateways: list[NatGateway] = Field(default_factory=list)
    peering_connections: list[VpcPeeringConnection] = Field(default_factory=list)
    flow_logs_enabled: bool = False
    tags: dict = Field(default_factory=dict)


class TGWAttachment(BaseModel):
    id: str
    resource_id: str               # vpc-xxx | vpn-xxx | dx-xxx
    resource_type: AttachmentType
    resource_owner_account_id: str
    state: str
    association_route_table_id: Optional[str] = None


class TransitGateway(BaseModel):
    id: str
    name: Optional[str] = None
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
    name: Optional[str] = None
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
    next_hop_type: str  # VirtualNetworkGateway | VnetLocal | Internet | VirtualAppliance | None
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
    discovery_blocked: bool = False
    block_reason: Optional[str] = None


class AzureTopology(BaseModel):
    schema_version: str = TOPOLOGY_SCHEMA_VERSION
    engagement_id: str
    tenant_id: str
    management_groups: list[ManagementGroup] = Field(default_factory=list)
    subscriptions: list[AzureSubscriptionTopology] = Field(default_factory=list)
