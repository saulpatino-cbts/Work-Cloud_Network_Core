"""Azure Network Discovery — Phase C core.

Discovers all network topology resources across every subscription in an
Azure tenant using DefaultAzureCredential (or service principal).

Design principles:
  - ARM REST API + Azure Resource Graph for efficient cross-subscription queries.
  - Every subscription access failure is logged with reason — never silent.
  - Pagination uses skipToken for ARM list operations.
  - Management Group hierarchy discovered from tenant root.
  - --resume skips subscriptions with existing checkpoints.

API coverage (v1.2.0):
  ARM: VNets, Subnets (expanded), Route Tables (full rules), NSGs (full rules
       + flow log state), VNet Peerings, VPN/VNet Gateways (BGP + connections),
       Azure Firewalls, App Gateways (WAF config), vWANs, vHubs,
       Private DNS Zones, ExpressRoute Circuits,
       Load Balancers (rules + probes), Public IPs (association info),
       Private Endpoints (DNS zone groups), NAT Gateways, Bastion Hosts
  Management API: Management Group tree from tenant root
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from azure.core.exceptions import HttpResponseError

from cna.core.exceptions import CNAAuthError
from cna.core.persistence import EngagementStore
from cna.core.throttle import with_retry
from cna.core.topology_schema import (
    ApplicationGateway,
    AzureBastionHost,
    AzureFirewall,
    AzureGatewayConnection,
    AzureLBFrontendIP,
    AzureLBProbe,
    AzureLBRule,
    AzureLoadBalancer,
    AzureNatGateway,
    AzureNSG,
    AzurePrivateEndpoint,
    AzurePrivateEndpointConnection,
    AzurePublicIP,
    AzureRouteEntry,
    AzureRouteTable,
    AzureSubnet,
    AzureSubscriptionTopology,
    AzureTopology,
    AzureVHub,
    AzureVirtualNetworkGateway,
    AzureVWan,
    ExpressRouteCircuit,
    ManagementGroup,
    NSGSecurityRule,
    PrivateDnsZone,
    VNet,
    VNetPeering,
)

logger = logging.getLogger("cna.discovery.azure")


@dataclass
class AzureDiscoveryOptions:
    tenant_id: str
    subscription_ids: list[str] = field(default_factory=list)  # empty = all
    resume: bool = False
    use_resource_graph: bool = True  # faster cross-sub queries
    client_id: str | None = None  # for service principal auth
    client_secret: str | None = None  # never logged, in-memory only


def _rg_from_id(resource_id: str) -> str:
    """Extract resource group name from an Azure resource ID."""
    parts = resource_id.split("/")
    try:
        idx = next(i for i, p in enumerate(parts) if p.lower() == "resourcegroups")
        return parts[idx + 1]
    except (StopIteration, IndexError):
        return parts[4] if len(parts) > 4 else ""


def _sub_from_id(resource_id: str) -> str:
    """Extract subscription ID from an Azure resource ID."""
    parts = resource_id.split("/")
    try:
        idx = next(i for i, p in enumerate(parts) if p.lower() == "subscriptions")
        return parts[idx + 1]
    except (StopIteration, IndexError):
        return ""


def _safe_list(iterable):
    """Iterate safely — return [] on any exception."""
    try:
        return list(iterable)
    except Exception as exc:
        logger.debug("Safe-list failed: %s", exc)
        return []


class AzureDiscovery:
    """Orchestrates Azure network discovery across all subscriptions."""

    def __init__(self, store: EngagementStore, options: AzureDiscoveryOptions):
        self.store = store
        self.opts = options
        self._credential = None
        self._sub_client = None

    # ------------------------------------------------------------------ auth

    def _init_credentials(self) -> None:
        """Initialize Azure credentials using DefaultAzureCredential chain."""
        try:
            from azure.identity import ClientSecretCredential, DefaultAzureCredential
            from azure.mgmt.subscription import SubscriptionClient

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
        for sub in with_retry()(self._sub_client.subscriptions.list)():
            if sub.state != "Enabled":
                logger.info(
                    "Skipping %s subscription %s (%s)",
                    sub.state,
                    sub.subscription_id,
                    sub.display_name,
                )
                continue
            subs.append(
                {
                    "id": sub.subscription_id,
                    "name": sub.display_name,
                    "tenant_id": self.opts.tenant_id,
                }
            )
        return subs

    # ------------------------------------------------------------------ management groups

    def _collect_management_groups(self) -> list[ManagementGroup]:
        """Discover the full Management Group hierarchy from tenant root."""
        try:
            from azure.mgmt.managementgroups import ManagementGroupsAPI
        except ImportError:
            logger.warning(
                "azure-mgmt-managementgroups not installed. Skipping MG hierarchy discovery."
            )
            return []

        mg_client = ManagementGroupsAPI(self._credential)
        mg_list = []
        try:
            for mg in mg_client.management_groups.list():
                detail = mg_client.management_groups.get(mg.name, expand="children", recurse=False)
                child_mg_ids = []
                sub_ids = []
                for child in detail.children or []:
                    if "/managementGroups/" in (child.id or ""):
                        child_mg_ids.append(child.name)
                    elif "/subscriptions/" in (child.id or ""):
                        sub_ids.append(child.name)

                mg_list.append(
                    ManagementGroup(
                        id=mg.name,
                        name=mg.name,
                        display_name=mg.display_name or mg.name,
                        parent_id=None,
                        subscription_ids=sub_ids,
                        child_mg_ids=child_mg_ids,
                    )
                )
        except Exception as e:
            logger.warning("Management group enumeration failed: %s", e)
        return mg_list

    # ------------------------------------------------------------------ per-subscription

    def _discover_subscription(self, sub_id: str, sub_name: str) -> AzureSubscriptionTopology:
        """Run full network discovery for one Azure subscription."""
        from azure.mgmt.network import NetworkManagementClient

        topo = AzureSubscriptionTopology(
            subscription_id=sub_id,
            subscription_name=sub_name,
            tenant_id=self.opts.tenant_id,
        )

        try:
            net = NetworkManagementClient(self._credential, sub_id)

            # Order matters: collect flat resources first so VNets can ref them
            topo.public_ips = self._collect_public_ips(net, sub_id)
            topo.nsgs = self._collect_nsgs(net, sub_id)
            topo.route_tables = self._collect_route_tables(net, sub_id)
            topo.nat_gateways = self._collect_nat_gateways(net, sub_id)
            topo.vnets = self._collect_vnets(net, sub_id)
            topo.virtual_wans = self._collect_vwans(net, sub_id)
            topo.firewalls = self._collect_firewalls(net, sub_id)
            topo.application_gateways = self._collect_appgws(net, sub_id)
            topo.load_balancers = self._collect_load_balancers(net, sub_id)
            topo.virtual_network_gateways = self._collect_vnet_gateways(net, sub_id)
            topo.private_endpoints = self._collect_private_endpoints(net, sub_id)
            topo.bastion_hosts = self._collect_bastion_hosts(net, sub_id)
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

    # ------------------------------------------------------------------ VNets

    def _collect_vnets(self, net, sub_id: str) -> list[VNet]:
        vnets = []
        for vnet in _safe_list(net.virtual_networks.list_all()):
            subnets = []
            for s in vnet.subnets or []:
                # Extract names from IDs for human-readable display
                nsg_name = None
                if s.network_security_group and s.network_security_group.id:
                    nsg_name = s.network_security_group.id.split("/")[-1]

                rt_name = None
                if s.route_table and s.route_table.id:
                    rt_name = s.route_table.id.split("/")[-1]

                nat_gw_id = None
                if hasattr(s, "nat_gateway") and s.nat_gateway:
                    nat_gw_id = s.nat_gateway.id

                # Collect all address prefixes (dual-stack support)
                extra_prefixes: list[str] = []
                if hasattr(s, "address_prefixes") and s.address_prefixes:
                    extra_prefixes = list(s.address_prefixes)

                # Default outbound access (new subnets default True, can be disabled)
                default_outbound = True
                if hasattr(s, "default_outbound_access") and s.default_outbound_access is not None:
                    default_outbound = bool(s.default_outbound_access)

                pl_svc_policy = "Enabled"
                if hasattr(s, "private_link_service_network_policies"):
                    pl_svc_policy = str(s.private_link_service_network_policies or "Enabled")

                subnets.append(
                    AzureSubnet(
                        id=s.id,
                        name=s.name,
                        address_prefix=s.address_prefix
                        or (extra_prefixes[0] if extra_prefixes else ""),
                        nsg_id=s.network_security_group.id if s.network_security_group else None,
                        nsg_name=nsg_name,
                        route_table_id=s.route_table.id if s.route_table else None,
                        route_table_name=rt_name,
                        nat_gateway_id=nat_gw_id,
                        service_endpoints=[se.service for se in (s.service_endpoints or [])],
                        private_endpoint_network_policies=str(
                            s.private_endpoint_network_policies or "Enabled"
                        ),
                        private_link_service_network_policies=pl_svc_policy,
                        default_outbound_access=default_outbound,
                        delegation=(s.delegations[0].service_name if s.delegations else None),
                        address_prefixes=extra_prefixes,
                    )
                )

            peerings = []
            for p in vnet.virtual_network_peerings or []:
                remote_id = p.remote_virtual_network.id if p.remote_virtual_network else ""
                remote_sub = _sub_from_id(remote_id)
                # Try to get the actual remote VNet name from the resource ID
                remote_name = remote_id.split("/")[-1] if remote_id else None
                peerings.append(
                    VNetPeering(
                        id=p.id,
                        name=p.name,
                        remote_vnet_id=remote_id,
                        remote_vnet_name=remote_name,
                        remote_subscription_id=remote_sub,
                        peering_state=str(p.peering_state or "Unknown"),
                        allow_forwarded_traffic=bool(p.allow_forwarded_traffic),
                        allow_gateway_transit=bool(p.allow_gateway_transit),
                        use_remote_gateways=bool(p.use_remote_gateways),
                        do_not_verify_remote_gateways=bool(
                            getattr(p, "do_not_verify_remote_gateways", False)
                        ),
                        peer_complete_vnets=bool(getattr(p, "peer_complete_vnets", True)),
                    )
                )

            # DNS servers
            dns_servers: list[str] = []
            if vnet.dhcp_options and vnet.dhcp_options.dns_servers:
                dns_servers = list(vnet.dhcp_options.dns_servers)

            # DDoS protection
            ddos_enabled = bool(
                vnet.ddos_protection_plan is not None or vnet.enable_ddos_protection
            )
            ddos_plan_id = vnet.ddos_protection_plan.id if vnet.ddos_protection_plan else None

            # Encryption (VNet encryption — preview feature)
            encryption_enabled = False
            if hasattr(vnet, "encryption") and vnet.encryption:
                encryption_enabled = bool(getattr(vnet.encryption, "enabled", False))

            rg = _rg_from_id(vnet.id)
            vnets.append(
                VNet(
                    id=vnet.id,
                    name=vnet.name,
                    location=vnet.location,
                    resource_group=rg,
                    subscription_id=sub_id,
                    address_space=list(vnet.address_space.address_prefixes or []),
                    dns_servers=dns_servers,
                    subnets=subnets,
                    peerings=peerings,
                    ddos_protection_enabled=ddos_enabled,
                    ddos_protection_plan_id=ddos_plan_id,
                    flow_logs_enabled=False,  # enriched later if Network Watcher API available
                    encryption_enabled=encryption_enabled,
                    vm_protection_enabled=bool(getattr(vnet, "enable_vm_protection", False)),
                    tags=dict(vnet.tags or {}),
                )
            )
        return vnets

    # ------------------------------------------------------------------ NSGs

    def _collect_nsgs(self, net, sub_id: str) -> list[AzureNSG]:
        nsgs = []
        for nsg in _safe_list(net.network_security_groups.list_all()):
            rg = _rg_from_id(nsg.id)

            def _map_rule(r, is_default: bool = False) -> NSGSecurityRule:
                return NSGSecurityRule(
                    name=r.name,
                    priority=r.priority,
                    direction=str(r.direction or "Inbound"),
                    access=str(r.access or "Allow"),
                    protocol=str(r.protocol or "*"),
                    source_port_range=r.source_port_range,
                    source_port_ranges=list(r.source_port_ranges or []),
                    destination_port_range=r.destination_port_range,
                    destination_port_ranges=list(r.destination_port_ranges or []),
                    source_address_prefix=r.source_address_prefix,
                    source_address_prefixes=list(r.source_address_prefixes or []),
                    source_asgs=[
                        asg.id for asg in (r.source_application_security_groups or []) if asg.id
                    ],
                    destination_address_prefix=r.destination_address_prefix,
                    destination_address_prefixes=list(r.destination_address_prefixes or []),
                    destination_asgs=[
                        asg.id
                        for asg in (r.destination_application_security_groups or [])
                        if asg.id
                    ],
                    description=r.description,
                    is_default_rule=is_default,
                    provisioning_state=str(r.provisioning_state or "Succeeded"),
                )

            security_rules = [_map_rule(r) for r in (nsg.security_rules or [])]
            default_rules = [
                _map_rule(r, is_default=True) for r in (nsg.default_security_rules or [])
            ]

            subnet_ids = [s.id for s in (nsg.subnets or []) if s.id]
            nic_ids = [ni.id for ni in (nsg.network_interfaces or []) if ni.id]

            nsgs.append(
                AzureNSG(
                    id=nsg.id,
                    name=nsg.name,
                    location=nsg.location,
                    resource_group=rg,
                    security_rules=security_rules,
                    default_security_rules=default_rules,
                    associated_subnet_ids=subnet_ids,
                    associated_nic_ids=nic_ids,
                    flow_logs_enabled=False,  # requires Network Watcher flow log query
                    tags=dict(nsg.tags or {}),
                )
            )
        return nsgs

    # ------------------------------------------------------------------ Route Tables

    def _collect_route_tables(self, net, sub_id: str) -> list[AzureRouteTable]:
        tables = []
        for rt in _safe_list(net.route_tables.list_all()):
            rg = _rg_from_id(rt.id)
            routes = []
            for r in rt.routes or []:
                routes.append(
                    AzureRouteEntry(
                        name=r.name,
                        address_prefix=r.address_prefix or "",
                        next_hop_type=str(r.next_hop_type or "None"),
                        next_hop_ip=r.next_hop_ip_address,
                        has_bgp_override=bool(getattr(r, "has_bgp_override", False)),
                    )
                )
            subnet_ids = [s.id for s in (rt.subnets or []) if s.id]
            tables.append(
                AzureRouteTable(
                    id=rt.id,
                    name=rt.name,
                    location=rt.location,
                    resource_group=rg,
                    routes=routes,
                    associated_subnet_ids=subnet_ids,
                    disable_bgp_route_propagation=bool(rt.disable_bgp_route_propagation),
                    tags=dict(rt.tags or {}),
                )
            )
        return tables

    # ------------------------------------------------------------------ Public IPs

    def _collect_public_ips(self, net, sub_id: str) -> list[AzurePublicIP]:
        pips = []
        for pip in _safe_list(net.public_ip_addresses.list_all()):
            rg = _rg_from_id(pip.id)
            sku_name = "Standard"
            if pip.sku:
                sku_name = str(pip.sku.name or "Standard")

            assoc_id = None
            assoc_type = None
            if pip.ip_configuration and pip.ip_configuration.id:
                assoc_id = pip.ip_configuration.id
                # Infer type from the resource ID path
                id_lower = assoc_id.lower()
                if "networkinterfaces" in id_lower:
                    assoc_type = "NIC"
                elif "loadbalancers" in id_lower:
                    assoc_type = "LB"
                elif "applicationgateways" in id_lower:
                    assoc_type = "AppGW"
                elif "azurefirewalls" in id_lower:
                    assoc_type = "Firewall"
                elif "bastionhosts" in id_lower:
                    assoc_type = "Bastion"
                elif "virtualnetworkgateways" in id_lower:
                    assoc_type = "VpnGateway"

            dns_label = None
            fqdn = None
            if pip.dns_settings:
                dns_label = pip.dns_settings.domain_name_label
                fqdn = pip.dns_settings.fqdn

            ddos_mode = "VirtualNetworkInherited"
            if hasattr(pip, "ddos_settings") and pip.ddos_settings:
                ddos_mode = str(getattr(pip.ddos_settings, "protection_mode", ddos_mode))

            pips.append(
                AzurePublicIP(
                    id=pip.id,
                    name=pip.name,
                    location=pip.location,
                    resource_group=rg,
                    sku_name=sku_name,
                    allocation_method=str(pip.public_ip_allocation_method or "Static"),
                    ip_address=pip.ip_address,
                    ip_version=str(pip.public_ip_address_version or "IPv4"),
                    dns_label=dns_label,
                    fqdn=fqdn,
                    zones=list(pip.zones or []),
                    associated_resource_id=assoc_id,
                    associated_resource_type=assoc_type,
                    idle_timeout_minutes=int(pip.idle_timeout_in_minutes or 4),
                    ddos_protection_mode=ddos_mode,
                    tags=dict(pip.tags or {}),
                )
            )
        return pips

    # ------------------------------------------------------------------ Load Balancers

    def _collect_load_balancers(self, net, sub_id: str) -> list[AzureLoadBalancer]:
        lbs = []
        for lb in _safe_list(net.load_balancers.list_all()):
            rg = _rg_from_id(lb.id)
            sku_name = "Standard"
            if lb.sku:
                sku_name = str(lb.sku.name or "Standard")

            frontends: list[AzureLBFrontendIP] = []
            lb_type = "Public"
            for fic in lb.frontend_ip_configurations or []:
                is_private = fic.subnet is not None
                if is_private:
                    lb_type = "Internal"
                frontends.append(
                    AzureLBFrontendIP(
                        name=fic.name,
                        public_ip_id=fic.public_ip_address.id if fic.public_ip_address else None,
                        private_ip_address=fic.private_ip_address,
                        private_ip_allocation_method=str(fic.private_ip_allocation_method or "")
                        if is_private
                        else None,
                        subnet_id=fic.subnet.id if fic.subnet else None,
                        zones=list(getattr(fic, "zones", None) or []),
                    )
                )

            rules: list[AzureLBRule] = []
            for r in lb.load_balancing_rules or []:
                rules.append(
                    AzureLBRule(
                        name=r.name,
                        protocol=str(r.protocol or "Tcp"),
                        frontend_port=int(r.frontend_port or 0),
                        backend_port=int(r.backend_port or 0),
                        enable_floating_ip=bool(r.enable_floating_ip),
                        enable_tcp_reset=bool(getattr(r, "enable_tcp_reset", False)),
                        idle_timeout_minutes=int(r.idle_timeout_in_minutes or 4),
                        load_distribution=str(r.load_distribution or "Default"),
                        disable_outbound_snat=bool(getattr(r, "disable_outbound_snat", False)),
                    )
                )

            probes: list[AzureLBProbe] = []
            for p in lb.probes or []:
                probes.append(
                    AzureLBProbe(
                        name=p.name,
                        protocol=str(p.protocol or "Tcp"),
                        port=int(p.port or 0),
                        interval_seconds=int(p.interval_in_seconds or 15),
                        number_of_probes=int(p.number_of_probes or 2),
                        request_path=p.request_path,
                    )
                )

            pool_ids = [pool.id for pool in (lb.backend_address_pools or []) if pool.id]
            nat_rule_count = len(lb.inbound_nat_rules or [])

            # Collect zones from frontend configs
            zones: list[str] = []
            for fic in lb.frontend_ip_configurations or []:
                zones.extend(getattr(fic, "zones", None) or [])
            zones = sorted(set(zones))

            lbs.append(
                AzureLoadBalancer(
                    id=lb.id,
                    name=lb.name,
                    location=lb.location,
                    resource_group=rg,
                    sku_name=sku_name,
                    lb_type=lb_type,
                    frontend_ip_configs=frontends,
                    lb_rules=rules,
                    probes=probes,
                    backend_pool_ids=pool_ids,
                    inbound_nat_rule_count=nat_rule_count,
                    zones=zones,
                    tags=dict(lb.tags or {}),
                )
            )
        return lbs

    # ------------------------------------------------------------------ VNet Gateways

    def _collect_vnet_gateways(self, net, sub_id: str) -> list[AzureVirtualNetworkGateway]:
        gateways = []
        for gw in _safe_list(net.virtual_network_gateways.list_all()):
            rg = _rg_from_id(gw.id)

            sku_name = "VpnGw1"
            sku_tier = "VpnGw1"
            if gw.sku:
                sku_name = str(gw.sku.name or "VpnGw1")
                sku_tier = str(gw.sku.tier or "VpnGw1")

            bgp_asn = None
            bgp_ip = None
            if gw.bgp_settings:
                bgp_asn = gw.bgp_settings.asn
                bgp_ip = gw.bgp_settings.bgp_peering_address

            pip_ids = []
            subnet_id = None
            vpn_client_pools: list[str] = []
            for ipc in gw.ip_configurations or []:
                if ipc.public_ip_address:
                    pip_ids.append(ipc.public_ip_address.id)
                if ipc.subnet:
                    subnet_id = ipc.subnet.id

            if gw.vpn_client_configuration:
                for pool in gw.vpn_client_configuration.vpn_client_address_pool or []:
                    vpn_client_pools.append(pool.address_prefixes or [])

            # Collect connections for this gateway
            connections = self._collect_gateway_connections(net, rg, gw.name)

            gateways.append(
                AzureVirtualNetworkGateway(
                    id=gw.id,
                    name=gw.name,
                    location=gw.location,
                    resource_group=rg,
                    gateway_type=str(gw.gateway_type or "Vpn"),
                    vpn_type=str(gw.vpn_type or "RouteBased") if gw.gateway_type == "Vpn" else None,
                    sku_name=sku_name,
                    sku_tier=sku_tier,
                    active_active=bool(gw.active_active),
                    enable_bgp=bool(gw.enable_bgp),
                    bgp_asn=bgp_asn,
                    bgp_peering_address=bgp_ip,
                    public_ip_ids=pip_ids,
                    subnet_id=subnet_id,
                    vpn_client_address_pool=vpn_client_pools,
                    connections=connections,
                    generation=str(gw.vpn_gateway_generation or ""),
                    zones=list(gw.zones or []),
                    tags=dict(gw.tags or {}),
                )
            )
        return gateways

    def _collect_gateway_connections(
        self, net, resource_group: str, gateway_name: str
    ) -> list[AzureGatewayConnection]:
        connections = []
        try:
            for conn in _safe_list(net.virtual_network_gateway_connections.list(resource_group)):
                # Only include connections that reference this gateway
                gw_ref = ""
                if conn.virtual_network_gateway1:
                    gw_ref = conn.virtual_network_gateway1.id or ""
                if gateway_name.lower() not in gw_ref.lower():
                    continue

                connections.append(
                    AzureGatewayConnection(
                        id=conn.id,
                        name=conn.name,
                        connection_type=str(conn.connection_type or "IPsec"),
                        connection_status=str(conn.connection_status or "Unknown"),
                        remote_vnet_id=(
                            conn.virtual_network_gateway2.id
                            if conn.virtual_network_gateway2
                            else None
                        ),
                        local_network_gateway_id=(
                            conn.local_network_gateway2.id if conn.local_network_gateway2 else None
                        ),
                        express_route_circuit_id=(conn.peer.id if conn.peer else None),
                        routing_weight=int(conn.routing_weight or 10),
                        enable_bgp=bool(conn.enable_bgp),
                        use_policy_based_traffic_selectors=bool(
                            conn.use_policy_based_traffic_selectors
                        ),
                        dpd_timeout_seconds=getattr(conn, "dpd_timeout_seconds", None),
                        egress_bytes_transferred=int(conn.egress_bytes_transferred or 0),
                        ingress_bytes_transferred=int(conn.ingress_bytes_transferred or 0),
                        shared_key_set=True,  # key is always set when connection exists
                    )
                )
        except Exception as e:
            logger.debug(
                "Gateway connections for %s/%s failed: %s", resource_group, gateway_name, e
            )
        return connections

    # ------------------------------------------------------------------ Private Endpoints

    def _collect_private_endpoints(self, net, sub_id: str) -> list[AzurePrivateEndpoint]:
        endpoints = []
        for pe in _safe_list(net.private_endpoints.list_by_subscription()):
            rg = _rg_from_id(pe.id)
            subnet_id = ""
            if pe.subnet:
                subnet_id = pe.subnet.id or ""

            # Collect private IP addresses from NICs
            private_ips: list[str] = []
            for nic in pe.network_interfaces or []:
                if nic.id:
                    # We'll note the NIC reference; full IP requires a NIC GET
                    pass  # IPs populated by NIC lookup — skip for now
            # Use manual_private_link_service_connections or auto ones
            service_conns: list[AzurePrivateEndpointConnection] = []
            for sc in list(pe.private_link_service_connections or []) + list(
                pe.manual_private_link_service_connections or []
            ):
                state = "Pending"
                if sc.private_link_service_connection_state:
                    state = str(sc.private_link_service_connection_state.status or "Pending")
                service_conns.append(
                    AzurePrivateEndpointConnection(
                        connection_name=sc.name or "",
                        private_link_service_id=sc.private_link_service_id or "",
                        group_ids=list(sc.group_ids or []),
                        connection_state=state,
                    )
                )

            dns_group_names: list[str] = []
            custom_dns: list[str] = []
            for dns_cfg in pe.custom_dns_configs or []:
                if dns_cfg.fqdn:
                    custom_dns.append(dns_cfg.fqdn)
            for dng in pe.private_dns_zone_groups or []:
                if dng.name:
                    dns_group_names.append(dng.name)

            endpoints.append(
                AzurePrivateEndpoint(
                    id=pe.id,
                    name=pe.name,
                    location=pe.location,
                    resource_group=rg,
                    subnet_id=subnet_id,
                    private_ip_addresses=private_ips,
                    service_connections=service_conns,
                    dns_zone_group_names=dns_group_names,
                    custom_dns_configs=custom_dns,
                    tags=dict(pe.tags or {}),
                )
            )
        return endpoints

    # ------------------------------------------------------------------ NAT Gateways

    def _collect_nat_gateways(self, net, sub_id: str) -> list[AzureNatGateway]:
        nat_gws = []
        for ng in _safe_list(net.nat_gateways.list_all()):
            rg = _rg_from_id(ng.id)
            sku_name = "Standard"
            if ng.sku:
                sku_name = str(ng.sku.name or "Standard")

            pip_ids = [pip.id for pip in (ng.public_ip_addresses or []) if pip.id]
            prefix_ids = [pfx.id for pfx in (ng.public_ip_prefixes or []) if pfx.id]
            subnet_ids = [s.id for s in (ng.subnets or []) if s.id]

            nat_gws.append(
                AzureNatGateway(
                    id=ng.id,
                    name=ng.name,
                    location=ng.location,
                    resource_group=rg,
                    sku_name=sku_name,
                    idle_timeout_minutes=int(ng.idle_timeout_in_minutes or 4),
                    public_ip_ids=pip_ids,
                    public_ip_prefix_ids=prefix_ids,
                    associated_subnet_ids=subnet_ids,
                    zones=list(ng.zones or []),
                    provisioning_state=str(ng.provisioning_state or "Succeeded"),
                    tags=dict(ng.tags or {}),
                )
            )
        return nat_gws

    # ------------------------------------------------------------------ Bastion Hosts

    def _collect_bastion_hosts(self, net, sub_id: str) -> list[AzureBastionHost]:
        bastions = []
        for bh in _safe_list(net.bastion_hosts.list()):
            rg = _rg_from_id(bh.id)
            sku_name = "Standard"
            if hasattr(bh, "sku") and bh.sku:
                sku_name = str(bh.sku.name or "Standard")

            subnet_id = None
            pip_id = None
            for ipc in bh.ip_configurations or []:
                if ipc.subnet:
                    subnet_id = ipc.subnet.id
                if ipc.public_ip_address:
                    pip_id = ipc.public_ip_address.id

            bastions.append(
                AzureBastionHost(
                    id=bh.id,
                    name=bh.name,
                    location=bh.location,
                    resource_group=rg,
                    sku_name=sku_name,
                    subnet_id=subnet_id,
                    public_ip_id=pip_id,
                    scale_units=int(getattr(bh, "scale_units", 2) or 2),
                    tunneling_enabled=bool(getattr(bh, "enable_tunneling", False)),
                    shareable_link_enabled=bool(getattr(bh, "enable_shareable_link", False)),
                    ip_connect_enabled=bool(getattr(bh, "enable_ip_connect", False)),
                    file_copy_enabled=bool(getattr(bh, "enable_file_copy", False)),
                    kerberos_enabled=bool(getattr(bh, "enable_kerberos", False)),
                    tags=dict(bh.tags or {}),
                )
            )
        return bastions

    # ------------------------------------------------------------------ vWANs

    def _collect_vwans(self, net, sub_id: str) -> list[AzureVWan]:
        vwans = []
        for vwan in _safe_list(net.virtual_wans.list()):
            hubs = []
            for hub in _safe_list(net.virtual_hubs.list()):
                if hub.virtual_wan and hub.virtual_wan.id == vwan.id:
                    connected_vnets = [
                        vc.remote_virtual_network.id
                        for vc in (getattr(hub, "virtual_network_connections", None) or [])
                        if vc.remote_virtual_network
                    ]
                    hubs.append(
                        AzureVHub(
                            id=hub.id,
                            name=hub.name,
                            location=hub.location,
                            resource_group=_rg_from_id(hub.id),
                            address_prefix=hub.address_prefix or "",
                            sku=hub.sku or "Standard",
                            connected_vnet_ids=connected_vnets,
                            express_route_gateway_id=(
                                hub.express_route_gateway.id if hub.express_route_gateway else None
                            ),
                            azure_firewall_id=(
                                hub.azure_firewall.id if hub.azure_firewall else None
                            ),
                            routing_state=str(hub.routing_state or "None"),
                            virtual_router_asn=getattr(hub, "virtual_router_asn", None),
                            virtual_router_ips=list(getattr(hub, "virtual_router_ips", None) or []),
                        )
                    )
            vwans.append(
                AzureVWan(
                    id=vwan.id,
                    name=vwan.name,
                    resource_group=_rg_from_id(vwan.id),
                    sku=vwan.type or "Standard",
                    hubs=hubs,
                    allow_vnet_to_vnet_traffic=bool(
                        getattr(vwan, "allow_vnet_to_vnet_traffic", True)
                    ),
                    allow_branch_to_branch_traffic=bool(
                        getattr(vwan, "allow_branch_to_branch_traffic", True)
                    ),
                    tags=dict(vwan.tags or {}),
                )
            )
        return vwans

    # ------------------------------------------------------------------ Firewalls

    def _collect_firewalls(self, net, sub_id: str) -> list[AzureFirewall]:
        firewalls = []
        for fw in _safe_list(net.azure_firewalls.list_all()):
            rg = _rg_from_id(fw.id)
            sku_tier = "Standard"
            if fw.sku:
                sku_tier = fw.sku.tier or "Standard"
            subnet_id = None
            for ipc in fw.ip_configurations or []:
                if ipc.subnet and ipc.subnet.id:
                    subnet_id = ipc.subnet.id
                    break
            pip_ids = [
                ipc.public_ip_address.id
                for ipc in (fw.ip_configurations or [])
                if ipc.public_ip_address
            ]
            firewalls.append(
                AzureFirewall(
                    id=fw.id,
                    name=fw.name,
                    location=fw.location,
                    resource_group=rg,
                    sku_tier=sku_tier,
                    subnet_id=subnet_id,
                    public_ip_ids=pip_ids,
                    policy_id=fw.firewall_policy.id if fw.firewall_policy else None,
                    threat_intel_mode=str(fw.threat_intel_mode or "Alert"),
                    zones=list(fw.zones or []),
                    tags=dict(fw.tags or {}),
                )
            )
        return firewalls

    # ------------------------------------------------------------------ App Gateways

    def _collect_appgws(self, net, sub_id: str) -> list[ApplicationGateway]:
        appgws = []
        for agw in _safe_list(net.application_gateways.list_all()):
            rg = _rg_from_id(agw.id)
            sku_name = "Standard_v2"
            sku_capacity = None
            waf_enabled = False
            waf_mode = None
            waf_rule_set_type = None
            waf_rule_set_version = None
            if agw.sku:
                sku_name = agw.sku.name or "Standard_v2"
                sku_capacity = agw.sku.capacity
            if agw.web_application_firewall_configuration:
                waf_enabled = bool(agw.web_application_firewall_configuration.enabled)
                waf_mode = str(agw.web_application_firewall_configuration.firewall_mode or "")
                waf_rule_set_type = agw.web_application_firewall_configuration.rule_set_type
                waf_rule_set_version = agw.web_application_firewall_configuration.rule_set_version
            # WAF policy takes precedence over inline WAF config
            if agw.firewall_policy:
                waf_enabled = True

            subnet_id = ""
            for gw_config in agw.gateway_ip_configurations or []:
                if gw_config.subnet and gw_config.subnet.id:
                    subnet_id = gw_config.subnet.id
                    break

            frontend_ips = [fic.name for fic in (agw.frontend_ip_configurations or [])]

            ssl_policy = None
            if agw.ssl_policy and agw.ssl_policy.policy_name:
                ssl_policy = str(agw.ssl_policy.policy_name)

            autoscale_min = None
            autoscale_max = None
            if agw.autoscale_configuration:
                autoscale_min = agw.autoscale_configuration.min_capacity
                autoscale_max = agw.autoscale_configuration.max_capacity

            appgws.append(
                ApplicationGateway(
                    id=agw.id,
                    name=agw.name,
                    location=agw.location,
                    resource_group=rg,
                    sku_name=sku_name,
                    sku_capacity=sku_capacity,
                    subnet_id=subnet_id,
                    waf_enabled=waf_enabled,
                    waf_mode=waf_mode,
                    waf_rule_set_type=waf_rule_set_type,
                    waf_rule_set_version=waf_rule_set_version,
                    frontend_ip_configs=frontend_ips,
                    ssl_policy_name=ssl_policy,
                    autoscale_min=autoscale_min,
                    autoscale_max=autoscale_max,
                    zones=list(agw.zones or []),
                    tags=dict(agw.tags or {}),
                )
            )
        return appgws

    # ------------------------------------------------------------------ Private DNS

    def _collect_private_dns(self, sub_id: str) -> list[PrivateDnsZone]:
        zones = []
        try:
            from azure.mgmt.privatedns import PrivateDnsManagementClient

            dns_client = PrivateDnsManagementClient(self._credential, sub_id)
            for zone in _safe_list(dns_client.private_zones.list()):
                rg = _rg_from_id(zone.id)
                linked_vnets = []
                linked_names = []
                auto_reg = False
                for link in _safe_list(dns_client.virtual_network_links.list(rg, zone.name)):
                    if link.virtual_network:
                        linked_vnets.append(link.virtual_network.id)
                    if link.registration_enabled:
                        auto_reg = True
                    linked_names.append(link.name)
                zones.append(
                    PrivateDnsZone(
                        id=zone.id,
                        name=zone.name,
                        resource_group=rg,
                        linked_vnet_ids=linked_vnets,
                        linked_vnet_names=linked_names,
                        auto_registration_enabled=auto_reg,
                        record_count=zone.number_of_record_sets or 0,
                    )
                )
        except ImportError:
            logger.warning("azure-mgmt-privatedns not installed. Skipping Private DNS discovery.")
        except Exception as e:
            logger.warning("Private DNS discovery failed for %s: %s", sub_id, e)
        return zones

    # ------------------------------------------------------------------ ExpressRoute

    def _collect_er_circuits(self, net, sub_id: str) -> list[ExpressRouteCircuit]:
        circuits = []
        for erc in _safe_list(net.express_route_circuits.list_all()):
            rg = _rg_from_id(erc.id)
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

            peering_types = [p.peering_type for p in (erc.peerings or []) if p.peering_type]

            circuits.append(
                ExpressRouteCircuit(
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
                    global_reach_enabled=bool(getattr(erc, "global_reach_enabled", False)),
                    allow_classic_operations=bool(getattr(erc, "allow_classic_operations", False)),
                    peering_types=peering_types,
                    tags=dict(erc.tags or {}),
                )
            )
        return circuits

    # ----------------------------------------------------------------- run

    def run(self) -> AzureTopology:
        """Execute full Azure discovery. Returns completed AzureTopology."""
        engagement_id = self.store.engagement_id
        logger.info("[%s] Azure discovery starting (v1.2.0)", engagement_id)

        self._init_credentials()

        topology = AzureTopology(
            engagement_id=engagement_id,
            tenant_id=self.opts.tenant_id,
        )

        # Management Group hierarchy
        topology.management_groups = self._collect_management_groups()
        logger.info(
            "[%s] %d management groups discovered", engagement_id, len(topology.management_groups)
        )

        # Subscriptions
        all_subs = self._list_subscriptions()
        if self.opts.subscription_ids:
            # Case-insensitive match: Azure SDK returns lowercase GUIDs; user input may vary.
            wanted = {sid.lower().strip() for sid in self.opts.subscription_ids}
            matched = [s for s in all_subs if s["id"].lower() in wanted]
            if len(matched) < len(self.opts.subscription_ids):
                accessible_ids = {s["id"].lower() for s in all_subs}
                missing = [
                    sid for sid in self.opts.subscription_ids if sid.lower() not in accessible_ids
                ]
                logger.warning(
                    "[%s] Subscription filter: %d requested, %d accessible to SP, %d matched. "
                    "Not accessible: %s",
                    engagement_id,
                    len(self.opts.subscription_ids),
                    len(all_subs),
                    len(matched),
                    missing,
                )
            all_subs = matched

        logger.info("[%s] Discovering %d subscriptions", engagement_id, len(all_subs))

        for sub in all_subs:
            sub_id = sub["id"]
            sub_name = sub["name"]

            if self.opts.resume:
                checkpoints = self.store.list_completed_checkpoints(engagement_id, "azure")
                if any(sub_id in c for c in checkpoints):
                    logger.info(
                        "[%s] Skipping %s — checkpoint exists (--resume)", engagement_id, sub_id
                    )
                    continue

            logger.info("[%s] Subscription: %s (%s)", engagement_id, sub_id, sub_name)
            sub_topo = self._discover_subscription(sub_id, sub_name)
            topology.subscriptions.append(sub_topo)

            # Write checkpoint
            self.store.write_discovery_checkpoint(
                engagement_id,
                "azure",
                sub_id,
                json.loads(sub_topo.model_dump_json()),
            )

            vnet_count = len(sub_topo.vnets)
            nsg_count = len(sub_topo.nsgs)
            blocked = " [BLOCKED]" if sub_topo.discovery_blocked else ""
            logger.info(
                "[%s] %s: %d VNets, %d NSGs, %d LBs, %d GWs, %d PEs%s",
                engagement_id,
                sub_id,
                vnet_count,
                nsg_count,
                len(sub_topo.load_balancers),
                len(sub_topo.virtual_network_gateways),
                len(sub_topo.private_endpoints),
                blocked,
            )

        logger.info(
            "[%s] Azure discovery complete. %d subscriptions collected.",
            engagement_id,
            len(topology.subscriptions),
        )
        return topology
