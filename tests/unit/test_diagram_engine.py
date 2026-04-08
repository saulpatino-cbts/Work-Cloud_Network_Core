"""Unit tests for Phase B diagram engine.

Tests generate valid draw.io XML and Mermaid from minimal topology fixtures.
No filesystem writes — all tests operate on string output only.
No draw.io CLI required.
"""

import pytest

from cna.core.topology_schema import (
    VPC,
    AWSRegionTopology,
    AWSTopology,
    AzureSubnet,
    AzureSubscriptionTopology,
    AzureTopology,
    AzureVHub,
    AzureVWan,
    ManagementGroup,
    Subnet,
    SubnetType,
    TransitGateway,
    VNet,
)
from cna.diagram_engine.drawio_generator import (
    generate_tgw_topology,
    generate_vnet_topology,
    generate_vpc_topology,
    generate_vwan_topology,
)
from cna.diagram_engine.mermaid_generator import (
    generate_aws_account_hierarchy,
    generate_azure_mg_hierarchy,
    generate_landing_zone_diagram,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_vpc_region():
    return AWSRegionTopology(
        account_id="123456789012",
        region="us-east-1",
        vpcs=[
            VPC(
                id="vpc-abc123",
                name="prod-vpc",
                cidr="10.0.0.0/16",
                subnets=[
                    Subnet(
                        id="subnet-a",
                        name="public-a",
                        cidr="10.0.1.0/24",
                        az="us-east-1a",
                        subnet_type=SubnetType.PUBLIC,
                    ),
                    Subnet(
                        id="subnet-b",
                        name="private-b",
                        cidr="10.0.2.0/24",
                        az="us-east-1b",
                        subnet_type=SubnetType.PRIVATE,
                    ),
                ],
            )
        ],
    )


@pytest.fixture
def empty_vpc_region():
    return AWSRegionTopology(account_id="111111111111", region="eu-west-1", vpcs=[])


@pytest.fixture
def blocked_region():
    return AWSRegionTopology(
        account_id="222222222222",
        region="ap-southeast-1",
        discovery_blocked=True,
        block_reason="SCP denied ec2:DescribeVpcs",
    )


@pytest.fixture
def minimal_vnet_sub():
    return AzureSubscriptionTopology(
        subscription_id="sub-001",
        tenant_id="tenant-001",
        vnets=[
            VNet(
                id="/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/prod-vnet",
                name="prod-vnet",
                location="eastus",
                resource_group="rg-prod",
                subscription_id="sub-001",
                address_space=["10.1.0.0/16"],
                subnets=[
                    AzureSubnet(id="sn-001", name="app-subnet", address_prefix="10.1.1.0/24"),
                    AzureSubnet(
                        id="sn-002",
                        name="db-subnet",
                        address_prefix="10.1.2.0/24",
                        nsg_id="/nsg/db-nsg",
                    ),
                ],
            )
        ],
    )


# ── draw.io generator tests ──────────────────────────────────────────────


class TestVpcTopology:
    def test_produces_valid_xml(self, minimal_vpc_region):
        xml = generate_vpc_topology(minimal_vpc_region)
        assert xml.startswith("<mxfile")
        assert "</mxfile>" in xml

    def test_contains_vpc_name(self, minimal_vpc_region):
        xml = generate_vpc_topology(minimal_vpc_region)
        assert "prod-vpc" in xml

    def test_contains_subnet_cidr(self, minimal_vpc_region):
        xml = generate_vpc_topology(minimal_vpc_region)
        assert "10.0.1.0/24" in xml
        assert "10.0.2.0/24" in xml

    def test_public_subnet_style(self, minimal_vpc_region):
        xml = generate_vpc_topology(minimal_vpc_region)
        # Public subnets get yellow fill
        assert "fff2cc" in xml

    def test_private_subnet_style(self, minimal_vpc_region):
        xml = generate_vpc_topology(minimal_vpc_region)
        # Private subnets get red fill
        assert "f8cecc" in xml

    def test_empty_region_produces_note(self, empty_vpc_region):
        xml = generate_vpc_topology(empty_vpc_region)
        assert "No VPCs found" in xml
        assert "</mxfile>" in xml

    def test_blocked_region_raises(self, blocked_region):
        with pytest.raises(ValueError, match="Discovery was blocked"):
            generate_vpc_topology(blocked_region)

    def test_xml_safe_characters(self):
        """Resource names with XML-unsafe chars must not break output."""
        region = AWSRegionTopology(
            account_id="123456789012",
            region="us-east-1",
            vpcs=[
                VPC(
                    id="vpc-special",
                    name='VPC <Dev> & "Test" / Env',
                    cidr="10.99.0.0/16",
                )
            ],
        )
        xml = generate_vpc_topology(region)
        # Should not raise and should contain escaped version
        assert "&lt;Dev&gt;" in xml or "VPC" in xml
        assert "</mxfile>" in xml

    def test_large_vpc_many_subnets(self):
        """20 subnets should not crash or produce malformed XML."""
        subnets = [
            Subnet(
                id=f"sn-{i}", cidr=f"10.0.{i}.0/24", az="us-east-1a", subnet_type=SubnetType.PRIVATE
            )
            for i in range(20)
        ]
        region = AWSRegionTopology(
            account_id="123456789012",
            region="us-east-1",
            vpcs=[VPC(id="vpc-big", name="big-vpc", cidr="10.0.0.0/8", subnets=subnets)],
        )
        xml = generate_vpc_topology(region)
        assert xml.count("mxCell") > 20
        assert "</mxfile>" in xml


class TestVnetTopology:
    def test_produces_valid_xml(self, minimal_vnet_sub):
        xml = generate_vnet_topology(minimal_vnet_sub)
        assert xml.startswith("<mxfile")
        assert "</mxfile>" in xml

    def test_contains_vnet_name(self, minimal_vnet_sub):
        xml = generate_vnet_topology(minimal_vnet_sub)
        assert "prod-vnet" in xml

    def test_nsg_indicator(self, minimal_vnet_sub):
        xml = generate_vnet_topology(minimal_vnet_sub)
        # db-subnet has NSG, app-subnet does not
        assert "🔒" in xml  # has NSG
        assert "⚠️" in xml  # missing NSG

    def test_empty_subscription_produces_note(self):
        sub = AzureSubscriptionTopology(subscription_id="sub-empty", tenant_id="t-001", vnets=[])
        xml = generate_vnet_topology(sub)
        assert "No VNets found" in xml

    def test_blocked_subscription_raises(self):
        sub = AzureSubscriptionTopology(
            subscription_id="sub-blocked",
            tenant_id="t-001",
            discovery_blocked=True,
            block_reason="Azure Policy denied",
        )
        with pytest.raises(ValueError, match="Discovery was blocked"):
            generate_vnet_topology(sub)


class TestTgwTopology:
    def test_produces_valid_xml(self, minimal_vpc_region):
        tgw = TransitGateway(
            id="tgw-abc",
            name="prod-tgw",
            owner_account_id="123456789012",
            attachments=[],
        )
        xml = generate_tgw_topology(tgw, minimal_vpc_region)
        assert "</mxfile>" in xml
        assert "prod-tgw" in xml


class TestVwanTopology:
    def test_produces_valid_xml(self):
        vwan = AzureVWan(
            id="/vwan/prod-vwan",
            name="prod-vwan",
            resource_group="rg-conn",
            sku="Standard",
            hubs=[
                AzureVHub(
                    id="/hub/us-hub",
                    name="us-hub",
                    location="eastus",
                    resource_group="rg-conn",
                    address_prefix="10.100.0.0/23",
                    routing_state="Provisioned",
                    connected_vnet_ids=["/vnets/spoke-1", "/vnets/spoke-2"],
                )
            ],
        )
        xml = generate_vwan_topology(vwan)
        assert "</mxfile>" in xml
        assert "us-hub" in xml

    def test_empty_vwan_produces_note(self):
        vwan = AzureVWan(
            id="/vwan/empty", name="empty-vwan", resource_group="rg-conn", sku="Standard", hubs=[]
        )
        xml = generate_vwan_topology(vwan)
        assert "no hubs" in xml.lower()


# ── Mermaid generator tests ──────────────────────────────────────────────


class TestMermaidGenerators:
    def test_aws_hierarchy_starts_with_flowchart(self):
        from cna.core.topology_schema import AWSAccount

        topology = AWSTopology(
            engagement_id="eng-001",
            management_account_id="000000000000",
            accounts=[
                AWSAccount(account_id="000000000000", is_management_account=True),
                AWSAccount(account_id="111111111111", account_name="prod", ou_name="Production"),
                AWSAccount(account_id="222222222222", account_name="dev", ou_name="Development"),
            ],
        )
        mmd = generate_aws_account_hierarchy(topology)
        assert mmd.startswith("flowchart TD")
        assert "000000000000" in mmd
        assert "Production" in mmd
        assert "Development" in mmd

    def test_azure_mg_hierarchy_starts_with_flowchart(self):
        topology = AzureTopology(
            engagement_id="eng-001",
            tenant_id="tenant-001",
            management_groups=[
                ManagementGroup(
                    id="mg-root",
                    name="root",
                    display_name="Root",
                    child_mg_ids=["mg-prod"],
                ),
                ManagementGroup(
                    id="mg-prod",
                    name="prod",
                    display_name="Production",
                    parent_id="mg-root",
                    subscription_ids=["sub-001", "sub-002"],
                ),
            ],
        )
        mmd = generate_azure_mg_hierarchy(topology)
        assert mmd.startswith("flowchart TD")
        assert "Production" in mmd
        assert "sub-001" in mmd

    def test_lz_diagram_flowchart_lr(self):
        mmd = generate_landing_zone_diagram(
            platform="aws",
            design_notes={
                "management_layer": "Management Account",
                "connectivity_layer": "Transit Gateway",
                "workload_layers": ["Prod Workloads", "Dev Workloads"],
                "security_controls": ["Network Firewall", "GuardDuty"],
            },
        )
        assert mmd.startswith("flowchart LR")
        assert "Transit_Gateway" in mmd or "Transit" in mmd
        assert "Network_Firewall" in mmd or "Network" in mmd

    def test_empty_topology_does_not_crash(self):
        topology = AWSTopology(engagement_id="eng-empty", accounts=[])
        mmd = generate_aws_account_hierarchy(topology)
        assert "EMPTY" in mmd or "No accounts" in mmd
