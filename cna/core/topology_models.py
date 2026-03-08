"""Topology input contracts for the diagram engine.

Phase B fix for TODO_PhaseA DD: no enforced data contract between
discovery engine and diagram generators. Every generator accepts
a typed Pydantic model, not a raw dict.

Discovery engine (Phase C) MUST output these models.
Diagram generators MUST accept only these models.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class SubnetType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ISOLATED = "isolated"  # no route to internet, no NAT
    TRANSIT = "transit"    # TGW attachment subnet


class PeeringState(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    EXPIRED = "expired"


class FirewallMode(str, Enum):
    INLINE = "inline"       # traffic routed through
    PARALLEL = "parallel"   # monitoring only
    NONE = "none"


class RegionGroup(str, Enum):
    US = "us"
    EMEA = "emea"
    JAPAN = "japan"
    OTHER = "other"


# ── AWS Topology Models ────────────────────────────────────────────────────

class AWSSubnet(BaseModel):
    id: str
    cidr: str
    az: str
    type: SubnetType
    name: Optional[str] = None
    route_table_id: Optional[str] = None


class AWSRouteTable(BaseModel):
    id: str
    routes: list[dict] = Field(default_factory=list)  # [{cidr, target, type}]
    associated_subnets: list[str] = Field(default_factory=list)
    is_main: bool = False


class AWSInternetGateway(BaseModel):
    id: str
    state: str = "attached"


class AWSNatGateway(BaseModel):
    id: str
    subnet_id: str
    state: str
    public_ip: Optional[str] = None


class AWSVPCPeeringConnection(BaseModel):
    id: str
    requester_vpc_id: str
    accepter_vpc_id: str
    requester_account_id: str
    accepter_account_id: str
    state: PeeringState


class AWSTransitGatewayAttachment(BaseModel):
    id: str
    tgw_id: str
    resource_type: str  # vpc | vpn | direct-connect-gateway | peering
    resource_id: str
    account_id: str
    state: str


class AWSTransitGateway(BaseModel):
    id: str
    name: Optional[str] = None
    account_id: str
    region: str
    attachments: list[AWSTransitGatewayAttachment] = Field(default_factory=list)
    route_tables: list[dict] = Field(default_factory=list)


class AWSVPC(BaseModel):
    id: str
    cidr: str
    name: Optional[str] = None
    account_id: str
    region: str
    is_default: bool = False
    subnets: list[AWSSubnet] = Field(default_factory=list)
    route_tables: list[AWSRouteTable] = Field(default_factory=list)
    internet_gateway: Optional[AWSInternetGateway] = None
    nat_gateways: list[AWSNatGateway] = Field(default_factory=list)
    peering_connections: list[AWSVPCPeeringConnection] = Field(default_factory=list)
    tgw_attachments: list[str] = Field(default_factory=list)  # attachment IDs
    firewall_mode: FirewallMode = FirewallMode.NONE
    firewall_subnet_ids: list[str] = Field(default_factory=list)


class AWSAccount(BaseModel):
    account_id: str
    name: Optional[str] = None
    organizational_unit: Optional[str] = None
    is_management: bool = False


class AWSRegionTopology(BaseModel):
    account_id: str
    account_name: Optional[str] = None
    region: str
    region_group: RegionGroup
    vpcs: list[AWSVPC] = Field(default_factory=list)
    transit_gateways: list[AWSTransitGateway] = Field(default_factory=list)
    # discovery metadata
    discovery_complete: bool = False
    blocked_services: list[str] = Field(default_factory=list)
    block_reasons: list[str] = Field(default_factory=list)


class AWSOrganizationTopology(BaseModel):
    """Root topology model for AWS — spans all accounts and regions."""
    engagement_id: str
    management_account_id: str
    accounts: list[AWSAccount] = Field(default_factory=list)
    region_topologies: list[AWSRegionTopology] = Field(default_factory=list)
    transit_gateways: list[AWSTransitGateway] = Field(default_factory=list)


# ── Azure Topology Models ──────────────────────────────────────────────────

class AzureSubnet(BaseModel):
    id: str
    name: str
    address_prefix: str
    nsg_id: Optional[str] = None
    route_table_id: Optional[str] = None
    service_endpoints: list[str] = Field(default_factory=list)
    delegations: list[str] = Field(default_factory=list)


class AzureVNetPeering(BaseModel):
    id: str
    name: str
    remote_vnet_id: str
    remote_subscription_id: str
    allow_vnet_access: bool = True
    allow_forwarded_traffic: bool = False
    use_remote_gateways: bool = False
    state: str


class AzureVNet(BaseModel):
    id: str
    name: str
    subscription_id: str
    resource_group: str
    region: str
    region_group: RegionGroup
    address_spaces: list[str] = Field(default_factory=list)
    subnets: list[AzureSubnet] = Field(default_factory=list)
    peerings: list[AzureVNetPeering] = Field(default_factory=list)
    connected_to_hub: bool = False
    hub_id: Optional[str] = None
    firewall_present: bool = False
    firewall_id: Optional[str] = None
    firewall_mode: FirewallMode = FirewallMode.NONE
    ddos_protection: bool = False


class AzureVHub(BaseModel):
    id: str
    name: str
    address_prefix: str
    subscription_id: str
    region: str
    region_group: RegionGroup
    connected_vnets: list[str] = Field(default_factory=list)  # VNet IDs
    connected_vpn_sites: list[str] = Field(default_factory=list)
    azure_firewall_id: Optional[str] = None


class AzureVWan(BaseModel):
    id: str
    name: str
    subscription_id: str
    hubs: list[AzureVHub] = Field(default_factory=list)


class AzureSubscription(BaseModel):
    subscription_id: str
    name: str
    management_group_id: Optional[str] = None
    vnets: list[AzureVNet] = Field(default_factory=list)
    # discovery metadata
    discovery_complete: bool = False
    blocked_resource_types: list[str] = Field(default_factory=list)
    block_reasons: list[str] = Field(default_factory=list)


class AzureTenantTopology(BaseModel):
    """Root topology model for Azure — spans all subscriptions."""
    engagement_id: str
    tenant_id: str
    subscriptions: list[AzureSubscription] = Field(default_factory=list)
    virtual_wans: list[AzureVWan] = Field(default_factory=list)
    management_group_tree: dict = Field(default_factory=dict)
