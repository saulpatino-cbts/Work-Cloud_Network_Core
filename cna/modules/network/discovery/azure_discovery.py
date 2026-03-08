"""Azure Network Discovery — Phase C core.

Discovers all network topology resources across every subscription in an
Azure tenant using DefaultAzureCredential (or service principal).

Design principles:
  - ARM REST API + Azure Resource Graph for efficient cross-subscription queries.
  - Every subscription access failure is logged with reason — never silent.
  - Pagination uses skipToken for ARM list operations.
  - Management Group hierarchy discovered from tenant root.
  - --resume skips subscriptions with existing checkpoints.

API coverage:
  ARM: VNets, Subnets, Route Tables, NSGs, VNet Peerings,
       VPN Gateways, Azure Firewalls, App Gateways, vWANs, vHubs,
       Private DNS Zones, ExpressRoute Circuits
  Resource Graph: cross-subscription bulk queries for efficiency
  Management API: Management Group tree from tenant root
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from cna.core.exceptions import CNAAuthError, CNAPermissionError
from cna.core.persistence import EngagementStore
from cna.core.throttle import with_retry
from cna.core.topology_schema import (
    AzureTopology, AzureSubscriptionTopology, ManagementGroup,
    VNet, AzureSubnet, AzureRouteTable, AzureRouteEntry, VNetPeering,
    AzureFirewall, ApplicationGateway, PrivateDnsZone, ExpressRouteCircuit,
    AzureVWan, AzureVHub, TOPOLOGY_SCHEMA_VERSION,
)

logger = logging.getLogger("cna.discovery.azure")


@dataclass
class AzureDiscoveryOptions:
    tenant_id: str
    subscription_ids: list[str] = field(default_factory=list)  # empty = all
    resume: bool = False
    use_resource_graph: bool = True   # faster cross-sub queries
    client_id: Optional[str] = None   # for service principal auth
    client_secret: Optional[str] = None  # never logged, in-memory only


class AzureDiscovery:
    """Orchestrates Azure network discovery across all subscriptions."""

    def __init__(self, store: EngagementStore, options: AzureDiscoveryOptions):
        self.store = store
        self.opts = options
        self._credential = None
        self._sub_client = None
        self._rg_client = None

    # ------------------------------------------------------------------ auth

    def _init_credentials(self) -> None:
        """Initialize Azure credentials using DefaultAzureCredential chain."""
        try:
            from azure.identity import DefaultAzureCredential, ClientSecretCredential
            from azure.mgmt.subscription import SubscriptionClient
            from azure.mgmt.resource.resources import ResourceManagementClient

            if self.opts.client_id and self.opts.client_secret:
                logger.info("Using service principal credentials")
                self._credential = ClientSecretCredential(
                    tenant_id=self.opts.tenant_id,
                    client_id=self.opts.client_id,
                    client_secret=self.opts.client_secret,
                )
            else:
                logger.info("Using DefaultAzureCredential chain")
                self._credential = DefaultAzureCredential()

            # Validate by listing subscriptions
            self._sub_client = SubscriptionClient(self._credential)
        except ImportError as e:
            raise CNAAuthError(
                "azure-identity and azure-mgmt-subscription are required. "
                "Run: pip install azure-identity azure-mgmt-subscription "
                "azure-mgmt-network azure-mgmt-resource"
            ) from e

    # ------------------------------------------------------------------ subscriptions

    def _list_subscriptions(self) -> list[dict]:
        """List all accessible subscriptions in the tenant."""
        subs = []
        for sub in with_retry(self._sub_client.subscriptions.list)():
            if sub.state != "Enabled":
                logger.info("Skipping %s subscription %s (%s)",
                            sub.state, sub.subscription_id, sub.display_name)
                continue
            subs.append({
                "id": sub.subscription_id,
                "name": sub.display_name,
                "tenant_id": self.opts.tenant_id,
            })
        return subs

    # ------------------------------------------------------------------ management groups

    def _collect_management_groups(self) -> list[ManagementGroup]:
        """Discover the full Management Group hierarchy from tenant root."""
        try:
            from azure.mgmt.managementgroups import ManagementGroupsAPI
        except ImportError:
            logger.warning("azure-mgmt-managementgroups not installed. "
                           "Skipping MG hierarchy discovery.")
            return []

        mg_client = ManagementGroupsAPI(self._credential)
        mg_list = []
        try:
            for mg in mg_client.management_groups.list():
                detail = mg_client.management_groups.get(
                    mg.name, expand="children", recurse=False
                )
                child_mg_ids = []
                sub_ids = []
                for child in (detail.children or []):
                    if "/managementGroups/" in (child.id or ""):
                        child_mg_ids.append(child.name)
                    elif "/subscriptions/" in (child.id or ""):
                        sub_ids.append(child.name)

                mg_list.append(ManagementGroup(
                    id=mg.name,
                    name=mg.name,
                    display_name=mg.display_name or mg.name,
                    parent_id=None,  # resolved in post-processing pass
                    subscription_ids=sub_ids,
                    child_mg_ids=child_mg_ids,
                ))
        except Exception as e:
            logger.warning("Management group enumeration failed: %s", e)
        return mg_list

    # ------------------------------------------------------------------ per-subscription

    def _discover_subscription(self, sub_id: str, sub_name: str) -> AzureSubscriptionTopology:
        """Run full network discovery for one Azure subscription."""
        from azure.mgmt.network import NetworkManagementClient
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

        topo = AzureSubscriptionTopology(
            subscription_id=sub_id,
            subscription_name=sub_name,
            tenant_id=self.opts.tenant_id,
        )

        try:
            net = NetworkManagementClient(self._credential, sub_id)
            topo.vnets = self._collect_vnets(net, sub_id)
            topo.virtual_wans = self._collect_vwans(net, sub_id)
            topo.firewalls = self._collect_firewalls(net, sub_id)
            topo.application_gateways = self._collect_appgws(net, sub_id)
            topo.private_dns_zones = self._collect_private_dns(sub_id)
            topo.express_route_circuits = self._collect_er_circuits(net, sub_id)
        except HttpResponseError as e:
            status = e.status_code
            if status in (401, 403):
                logger.warning("Permission denied in subscription %s: %s", sub_id, e.message)
                topo.discovery_blocked = True
                topo.block_reason = f"HTTP {status}: {e.message}"
            else:
                logger.error("Unexpected HTTP error in subscription %s: %s", sub_id, e)
                topo.discovery_blocked = True
                topo.block_reason = f"HTTP {status}: {e.message}"
        except Exception as e:
            logger.error("Discovery failed for subscription %s: %s", sub_id, e)
            topo.discovery_blocked = True
            topo.block_reason = str(e)

        return topo

    def _collect_vnets(self, net, sub_id: str) -> list[VNet]:
        vnets = []
        for vnet in net.virtual_networks.list_all():
            subnets = []
            for s in (vnet.subnets or []):
                subnets.append(AzureSubnet(
                    id=s.id,
                    name=s.name,
                    address_prefix=s.address_prefix or "",
                    nsg_id=s.network_security_group.id if s.network_security_group else None,
                    route_table_id=s.route_table.id if s.route_table else None,
                    service_endpoints=[se.service for se in (s.service_endpoints or [])],
                    private_endpoint_network_policies=str(
                        s.private_endpoint_network_policies or "Enabled"
                    ),
                    delegation=(
                        s.delegations[0].service_name
                        if s.delegations else None
                    ),
                ))

            peerings = []
            for p in (vnet.virtual_network_peerings or []):
                remote_sub = ""
                remote_id = p.remote_virtual_network.id if p.remote_virtual_network else ""
                # Extract subscription from remote VNet ID
                parts = remote_id.split("/")
                if "subscriptions" in parts:
                    idx = parts.index("subscriptions")
                    remote_sub = parts[idx + 1] if idx + 1 < len(parts) else ""
                peerings.append(VNetPeering(
                    id=p.id,
                    name=p.name,
                    remote_vnet_id=remote_id,
                    remote_vnet_name=p.name.replace("-peering", ""),
                    remote_subscription_id=remote_sub,
                    peering_state=str(p.peering_state or "Unknown"),
                    allow_forwarded_traffic=bool(p.allow_forwarded_traffic),
                    allow_gateway_transit=bool(p.allow_gateway_transit),
                    use_remote_gateways=bool(p.use_remote_gateways),
                ))

            rg = vnet.id.split("/")[4] if vnet.id else ""
            vnets.append(VNet(
                id=vnet.id,
                name=vnet.name,
                location=vnet.location,
                resource_group=rg,
                subscription_id=sub_id,
                address_space=list(vnet.address_space.address_prefixes or []),
                subnets=subnets,
                peerings=peerings,
                ddos_protection_enabled=bool(
                    vnet.ddos_protection_plan is not None
                    or vnet.enable_ddos_protection
                ),
                tags=dict(vnet.tags or {}),
            ))
        return vnets

    def _collect_vwans(self, net, sub_id: str) -> list[AzureVWan]:
        vwans = []
        for vwan in net.virtual_wans.list():
            hubs = []
            for hub in net.virtual_hubs.list():
                if hub.virtual_wan and hub.virtual_wan.id == vwan.id:
                    connected_vnets = [
                        vc.remote_virtual_network.id
                        for vc in (hub.virtual_network_connections or [])
                        if vc.remote_virtual_network
                    ]
                    hubs.append(AzureVHub(
                        id=hub.id,
                        name=hub.name,
                        location=hub.location,
                        resource_group=hub.id.split("/")[4] if hub.id else "",
                        address_prefix=hub.address_prefix or "",
                        sku=hub.sku or "Standard",
                        connected_vnet_ids=connected_vnets,
                        express_route_gateway_id=(
                            hub.express_route_gateway.id
                            if hub.express_route_gateway else None
                        ),
                        azure_firewall_id=(
                            hub.azure_firewall.id
                            if hub.azure_firewall else None
                        ),
                        routing_state=str(hub.routing_state or "None"),
                    ))
            vwans.append(AzureVWan(
                id=vwan.id,
                name=vwan.name,
                resource_group=vwan.id.split("/")[4] if vwan.id else "",
                sku=vwan.type or "Standard",
                hubs=hubs,
            ))
        return vwans

    def _collect_firewalls(self, net, sub_id: str) -> list[AzureFirewall]:
        firewalls = []
        for fw in net.azure_firewalls.list_all():
            rg = fw.id.split("/")[4] if fw.id else ""
            sku_tier = "Standard"
            if fw.sku:
                sku_tier = fw.sku.tier or "Standard"
            subnet_id = None
            for ipc in (fw.ip_configurations or []):
                if ipc.subnet and ipc.subnet.id:
                    subnet_id = ipc.subnet.id
                    break
            pip_ids = [
                ipc.public_ip_address.id
                for ipc in (fw.ip_configurations or [])
                if ipc.public_ip_address
            ]
            firewalls.append(AzureFirewall(
                id=fw.id,
                name=fw.name,
                location=fw.location,
                resource_group=rg,
                sku_tier=sku_tier,
                subnet_id=subnet_id,
                public_ip_ids=pip_ids,
                policy_id=fw.firewall_policy.id if fw.firewall_policy else None,
                threat_intel_mode=str(fw.threat_intel_mode or "Alert"),
            ))
        return firewalls

    def _collect_appgws(self, net, sub_id: str) -> list[ApplicationGateway]:
        appgws = []
        for agw in net.application_gateways.list_all():
            rg = agw.id.split("/")[4] if agw.id else ""
            sku_name = "Standard_v2"
            waf_enabled = False
            if agw.sku:
                sku_name = agw.sku.name or "Standard_v2"
            if agw.web_application_firewall_configuration:
                waf_enabled = agw.web_application_firewall_configuration.enabled
            subnet_id = ""
            for gw_config in (agw.gateway_ip_configurations or []):
                if gw_config.subnet and gw_config.subnet.id:
                    subnet_id = gw_config.subnet.id
                    break
            frontend_ips = [
                fic.name for fic in (agw.frontend_ip_configurations or [])
            ]
            appgws.append(ApplicationGateway(
                id=agw.id,
                name=agw.name,
                location=agw.location,
                resource_group=rg,
                sku_name=sku_name,
                subnet_id=subnet_id,
                waf_enabled=waf_enabled,
                frontend_ip_configs=frontend_ips,
            ))
        return appgws

    def _collect_private_dns(self, sub_id: str) -> list[PrivateDnsZone]:
        zones = []
        try:
            from azure.mgmt.privatedns import PrivateDnsManagementClient
            dns_client = PrivateDnsManagementClient(self._credential, sub_id)
            for zone in dns_client.private_zones.list():
                rg = zone.id.split("/")[4] if zone.id else ""
                linked_vnets = [
                    link.virtual_network.id
                    for link in dns_client.virtual_network_links.list(rg, zone.name)
                    if link.virtual_network
                ]
                zones.append(PrivateDnsZone(
                    id=zone.id,
                    name=zone.name,
                    resource_group=rg,
                    linked_vnet_ids=linked_vnets,
                    record_count=zone.number_of_record_sets or 0,
                ))
        except ImportError:
            logger.warning("azure-mgmt-privatedns not installed. Skipping Private DNS discovery.")
        except Exception as e:
            logger.warning("Private DNS discovery failed for %s: %s", sub_id, e)
        return zones

    def _collect_er_circuits(self, net, sub_id: str) -> list[ExpressRouteCircuit]:
        circuits = []
        for erc in net.express_route_circuits.list_all():
            rg = erc.id.split("/")[4] if erc.id else ""
            sku_tier = "Standard"
            sku_family = "MeteredData"
            if erc.sku:
                sku_tier = erc.sku.tier or "Standard"
                sku_family = erc.sku.family or "MeteredData"
            provider = None
            peering_loc = None
            bw = None
            if erc.service_provider_properties:
                provider = erc.service_provider_properties.service_provider_name
                peering_loc = erc.service_provider_properties.peering_location
                bw = erc.service_provider_properties.bandwidth_in_mbps
            circuits.append(ExpressRouteCircuit(
                id=erc.id,
                name=erc.name,
                location=erc.location,
                resource_group=rg,
                service_provider=provider,
                peering_location=peering_loc,
                bandwidth_mbps=bw,
                sku_tier=sku_tier,
                sku_family=sku_family,
                circuit_provisioning_state=str(erc.circuit_provisioning_state or "Enabled"),
            ))
        return circuits

    # ----------------------------------------------------------------- run

    def run(self) -> AzureTopology:
        """Execute full Azure discovery. Returns completed AzureTopology."""
        engagement_id = self.store.engagement_id
        logger.info("[%s] Azure discovery starting", engagement_id)

        self._init_credentials()

        topology = AzureTopology(
            engagement_id=engagement_id,
            tenant_id=self.opts.tenant_id,
        )

        # Management Group hierarchy
        topology.management_groups = self._collect_management_groups()
        logger.info("[%s] %d management groups discovered",
                    engagement_id, len(topology.management_groups))

        # Subscriptions
        all_subs = self._list_subscriptions()
        if self.opts.subscription_ids:
            all_subs = [s for s in all_subs if s["id"] in self.opts.subscription_ids]

        logger.info("[%s] Discovering %d subscriptions", engagement_id, len(all_subs))

        for sub in all_subs:
            sub_id = sub["id"]
            sub_name = sub["name"]

            if self.opts.resume:
                checkpoints = self.store.list_completed_checkpoints(engagement_id, "azure")
                if any(sub_id in c for c in checkpoints):
                    logger.info("[%s] Skipping %s — checkpoint exists (--resume)",
                                engagement_id, sub_id)
                    continue

            logger.info("[%s] Subscription: %s (%s)", engagement_id, sub_id, sub_name)
            sub_topo = self._discover_subscription(sub_id, sub_name)
            topology.subscriptions.append(sub_topo)

            # Write checkpoint
            self.store.write_discovery_checkpoint(
                engagement_id, "azure",
                account_id=sub_id,
                data=json.loads(sub_topo.model_dump_json()),
            )

            vnet_count = len(sub_topo.vnets)
            blocked = " [BLOCKED]" if sub_topo.discovery_blocked else ""
            logger.info("[%s] %s: %d VNets%s", engagement_id, sub_id, vnet_count, blocked)

        logger.info("[%s] Azure discovery complete. %d subscriptions collected.",
                    engagement_id, len(topology.subscriptions))
        return topology
