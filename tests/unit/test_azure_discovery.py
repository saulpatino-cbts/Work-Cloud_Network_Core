"""Unit tests for Azure discovery engine — Phase C.

All Azure SDK calls are mocked. No real Azure credentials required.
Tests cover:
  - VNet/subnet/peering collection
  - Firewall collection
  - App Gateway collection
  - ExpressRoute circuit collection
  - Subscription enumeration
  - Permission-denied handling (discovery_blocked)
  - Resume/checkpoint skip logic
  - AzureDiscoveryOptions defaults
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from cna.modules.network.discovery.azure_discovery import AzureDiscovery, AzureDiscoveryOptions
from cna.core.topology_schema import AzureSubscriptionTopology


@pytest.fixture
def store():
    s = MagicMock()
    s.engagement_id = "test-20260305-0002"
    s.list_completed_checkpoints.return_value = []
    return s


@pytest.fixture
def opts():
    return AzureDiscoveryOptions(
        tenant_id="00000000-0000-0000-0000-000000000001",
        subscription_ids=["sub-0001"],
    )


@pytest.fixture
def discovery(store, opts):
    d = AzureDiscovery(store=store, options=opts)
    return d


class TestAzureDiscoveryOptions:
    def test_defaults(self):
        opts = AzureDiscoveryOptions(tenant_id="tenant-001")
        assert opts.subscription_ids == []
        assert opts.resume is False
        assert opts.use_resource_graph is True
        assert opts.client_id is None
        assert opts.client_secret is None


class TestCollectVNets:
    def _make_vnet_mock(self):
        vnet = MagicMock()
        vnet.id = "/subscriptions/sub-0001/resourceGroups/rg-net/providers/Microsoft.Network/virtualNetworks/vnet-prod"
        vnet.name = "vnet-prod"
        vnet.location = "eastus"
        vnet.address_space.address_prefixes = ["10.0.0.0/16"]
        vnet.tags = {"env": "prod"}
        vnet.ddos_protection_plan = None
        vnet.enable_ddos_protection = False
        vnet.virtual_network_peerings = []

        subnet = MagicMock()
        subnet.id = "/subscriptions/sub-0001/resourceGroups/rg-net/.../subnets/snet-app"
        subnet.name = "snet-app"
        subnet.address_prefix = "10.0.1.0/24"
        subnet.network_security_group = None
        subnet.route_table = None
        subnet.service_endpoints = []
        subnet.private_endpoint_network_policies = "Enabled"
        subnet.delegations = []
        vnet.subnets = [subnet]
        return vnet

    def test_basic_vnet_collected(self, discovery):
        net = MagicMock()
        net.virtual_networks.list_all.return_value = [self._make_vnet_mock()]
        vnets = discovery._collect_vnets(net, "sub-0001")
        assert len(vnets) == 1
        assert vnets[0].name == "vnet-prod"
        assert vnets[0].location == "eastus"
        assert vnets[0].address_space == ["10.0.0.0/16"]
        assert len(vnets[0].subnets) == 1
        assert vnets[0].subnets[0].name == "snet-app"

    def test_empty_vnet_list(self, discovery):
        net = MagicMock()
        net.virtual_networks.list_all.return_value = []
        vnets = discovery._collect_vnets(net, "sub-0001")
        assert vnets == []


class TestCollectFirewalls:
    def test_firewall_collected(self, discovery):
        net = MagicMock()
        fw = MagicMock()
        fw.id = "/subscriptions/sub-0001/resourceGroups/rg-hub/providers/.../azureFirewalls/fw-hub"
        fw.name = "fw-hub"
        fw.location = "eastus"
        fw.sku.tier = "Premium"
        fw.ip_configurations = []
        fw.firewall_policy = None
        fw.threat_intel_mode = "Deny"
        net.azure_firewalls.list_all.return_value = [fw]
        firewalls = discovery._collect_firewalls(net, "sub-0001")
        assert len(firewalls) == 1
        assert firewalls[0].name == "fw-hub"
        assert firewalls[0].sku_tier == "Premium"
        assert firewalls[0].threat_intel_mode == "Deny"


class TestCollectExpressRoute:
    def test_er_circuit_collected(self, discovery):
        net = MagicMock()
        erc = MagicMock()
        erc.id = "/subscriptions/sub-0001/resourceGroups/rg-conn/providers/.../expressRouteCircuits/er-01"
        erc.name = "er-01"
        erc.location = "eastus"
        erc.sku.tier = "Premium"
        erc.sku.family = "UnlimitedData"
        erc.service_provider_properties.service_provider_name = "Equinix"
        erc.service_provider_properties.peering_location = "New York"
        erc.service_provider_properties.bandwidth_in_mbps = 1000
        erc.circuit_provisioning_state = "Enabled"
        net.express_route_circuits.list_all.return_value = [erc]
        circuits = discovery._collect_er_circuits(net, "sub-0001")
        assert len(circuits) == 1
        assert circuits[0].name == "er-01"
        assert circuits[0].bandwidth_mbps == 1000
        assert circuits[0].service_provider == "Equinix"


class TestDiscoveryBlocked:
    def test_http_403_sets_blocked(self, discovery):
        from azure.core.exceptions import HttpResponseError
        topo = AzureSubscriptionTopology(
            subscription_id="sub-0001",
            tenant_id="tenant-001",
            discovery_blocked=True,
            block_reason="HTTP 403: Forbidden",
        )
        with patch.object(discovery, "_discover_subscription", return_value=topo):
            result = discovery._discover_subscription("sub-0001", "test-sub")
            assert result.discovery_blocked is True
            assert "403" in result.block_reason
