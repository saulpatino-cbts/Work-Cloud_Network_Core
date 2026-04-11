import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

// ── Expanded topology interfaces ──────────────────────────────────────────────

interface Subnet {
  id: string;
  name: string;
  address_prefix: string;
  nsg_id: string | null;
  nsg_name: string | null;
  route_table_id: string | null;
  route_table_name: string | null;
  nat_gateway_id: string | null;
  service_endpoints: string[];
  delegation: string | null;
  default_outbound_access: boolean;
  private_link_service_network_policies: string;
}

interface Peering {
  id: string;
  name: string;
  remote_vnet_name: string | null;
  remote_vnet_id: string;
  remote_subscription_id: string;
  peering_state: string;
  allow_forwarded_traffic: boolean;
  allow_gateway_transit: boolean;
  use_remote_gateways: boolean;
}

interface VNet {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  address_space: string[];
  dns_servers: string[];
  subnets: Subnet[];
  peerings: Peering[];
  ddos_protection_enabled: boolean;
  ddos_protection_plan_id: string | null;
  encryption_enabled: boolean;
  flow_logs_enabled: boolean;
  tags: Record<string, string>;
}

interface NSGRule {
  name: string;
  priority: number;
  direction: string;
  access: string;
  protocol: string;
  source_address_prefix: string | null;
  source_address_prefixes: string[];
  destination_address_prefix: string | null;
  destination_address_prefixes: string[];
  destination_port_range: string | null;
  destination_port_ranges: string[];
  is_default_rule: boolean;
  description: string | null;
}

interface NSG {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  security_rules: NSGRule[];
  associated_subnet_ids: string[];
  associated_nic_ids: string[];
  flow_logs_enabled: boolean;
  tags: Record<string, string>;
}

interface RouteEntry {
  name: string;
  address_prefix: string;
  next_hop_type: string;
  next_hop_ip: string | null;
}

interface RouteTable {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  routes: RouteEntry[];
  associated_subnet_ids: string[];
  disable_bgp_route_propagation: boolean;
}

interface Firewall {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_tier: string;
  threat_intel_mode: string;
  public_ip_ids: string[];
  zones: string[];
}

interface AppGateway {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_name: string;
  waf_enabled: boolean;
  waf_mode: string | null;
  waf_rule_set_type: string | null;
  waf_rule_set_version: string | null;
  zones: string[];
}

interface LoadBalancer {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_name: string;
  lb_type: string;
  lb_rules: { name: string; protocol: string; frontend_port: number; backend_port: number }[];
  probes: { name: string; protocol: string; port: number }[];
  zones: string[];
}

interface GatewayConnection {
  name: string;
  connection_type: string;
  connection_status: string;
  enable_bgp: boolean;
}

interface VNetGateway {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  gateway_type: string;
  vpn_type: string | null;
  sku_name: string;
  active_active: boolean;
  enable_bgp: boolean;
  bgp_asn: number | null;
  connections: GatewayConnection[];
  zones: string[];
}

interface PrivateEndpointConn {
  connection_name: string;
  private_link_service_id: string;
  group_ids: string[];
  connection_state: string;
}

interface PrivateEndpoint {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  subnet_id: string;
  service_connections: PrivateEndpointConn[];
  custom_dns_configs: string[];
}

interface PublicIP {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_name: string;
  allocation_method: string;
  ip_address: string | null;
  ip_version: string;
  zones: string[];
  associated_resource_type: string | null;
}

interface NatGateway {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  public_ip_ids: string[];
  associated_subnet_ids: string[];
  idle_timeout_minutes: number;
  zones: string[];
}

interface BastionHost {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_name: string;
  tunneling_enabled: boolean;
  shareable_link_enabled: boolean;
}

interface PrivateDnsZone {
  id: string;
  name: string;
  resource_group: string;
  linked_vnet_ids: string[];
  auto_registration_enabled: boolean;
  record_count: number;
}

interface ExpressRoute {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  service_provider: string | null;
  peering_location: string | null;
  bandwidth_mbps: number | null;
  sku_tier: string;
  circuit_provisioning_state: string;
  global_reach_enabled: boolean;
  peering_types: string[];
}

interface Subscription {
  subscription_id: string;
  subscription_name: string | null;
  discovery_blocked: boolean;
  block_reason: string | null;
  vnets: VNet[];
  nsgs: NSG[];
  route_tables: RouteTable[];
  firewalls: Firewall[];
  application_gateways: AppGateway[];
  load_balancers: LoadBalancer[];
  virtual_network_gateways: VNetGateway[];
  private_endpoints: PrivateEndpoint[];
  public_ips: PublicIP[];
  nat_gateways: NatGateway[];
  bastion_hosts: BastionHost[];
  private_dns_zones: PrivateDnsZone[];
  express_route_circuits: ExpressRoute[];
}

interface Topology {
  tenant_id: string;
  subscriptions: Subscription[];
}

// ── Platform subnets — don't flag for missing NSG ─────────────────────────────

const PLATFORM_SUBNETS = new Set([
  "GatewaySubnet",
  "AzureBastionSubnet",
  "AzureFirewallSubnet",
  "AzureFirewallManagementSubnet",
  "RouteServerSubnet",
]);

export default async function InventoryPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: { id: true, name: true, clientOrg: true, members: true },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  let topology: Topology | null = null;
  let jobDate: Date | null = null;
  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { topologyJson: true, completedAt: true },
    });
    if (job?.topologyJson) {
      try { topology = JSON.parse(job.topologyJson) as Topology; } catch { /* ignore */ }
    }
    jobDate = job?.completedAt ?? null;
  } catch { /* migration pending */ }

  if (!topology) {
    return (
      <div className="glass p-10 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-navy-100 dark:bg-navy-800">
          <svg className="h-6 w-6 text-navy-400 dark:text-navy-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
        </div>
        <p className="text-sm font-semibold text-navy-600 dark:text-navy-300">No inventory data yet</p>
        <p className="mt-1 text-xs text-navy-400 dark:text-navy-500">
          Run discovery on the{" "}
          <Link href={`/engagements/${id}/connections`} className="text-teal-600 hover:underline dark:text-teal-400">
            Connections
          </Link>{" "}
          tab to populate the network inventory.
        </p>
      </div>
    );
  }

  // ── Flatten all-subscription data ──────────────────────────────────────────
  const subs = topology.subscriptions;
  const allVnets     = subs.flatMap((s) => (s.vnets ?? []).map((v) => ({ ...v, _sub: s.subscription_name ?? s.subscription_id })));
  const allSubnets   = allVnets.flatMap((v) => (v.subnets ?? []).map((s) => ({ ...s, _vnet: v.name, _loc: v.location, _sub: v._sub })));
  const allNsgs      = subs.flatMap((s) => (s.nsgs ?? []).map((n) => ({ ...n, _sub: s.subscription_name ?? s.subscription_id })));
  const allRts       = subs.flatMap((s) => (s.route_tables ?? []).map((r) => ({ ...r, _sub: s.subscription_name ?? s.subscription_id })));
  const allFirewalls = subs.flatMap((s) => (s.firewalls ?? []).map((f) => ({ ...f, _sub: s.subscription_name ?? s.subscription_id })));
  const allAppGws    = subs.flatMap((s) => (s.application_gateways ?? []).map((a) => ({ ...a, _sub: s.subscription_name ?? s.subscription_id })));
  const allLbs       = subs.flatMap((s) => (s.load_balancers ?? []).map((l) => ({ ...l, _sub: s.subscription_name ?? s.subscription_id })));
  const allGws       = subs.flatMap((s) => (s.virtual_network_gateways ?? []).map((g) => ({ ...g, _sub: s.subscription_name ?? s.subscription_id })));
  const allPEs       = subs.flatMap((s) => (s.private_endpoints ?? []).map((p) => ({ ...p, _sub: s.subscription_name ?? s.subscription_id })));
  const allPIPs      = subs.flatMap((s) => (s.public_ips ?? []).map((p) => ({ ...p, _sub: s.subscription_name ?? s.subscription_id })));
  const allNats      = subs.flatMap((s) => (s.nat_gateways ?? []).map((n) => ({ ...n, _sub: s.subscription_name ?? s.subscription_id })));
  const allBastions  = subs.flatMap((s) => (s.bastion_hosts ?? []).map((b) => ({ ...b, _sub: s.subscription_name ?? s.subscription_id })));
  const allDnsZones  = subs.flatMap((s) => (s.private_dns_zones ?? []).map((z) => ({ ...z, _sub: s.subscription_name ?? s.subscription_id })));
  const allERs       = subs.flatMap((s) => (s.express_route_circuits ?? []).map((e) => ({ ...e, _sub: s.subscription_name ?? s.subscription_id })));

  const subnetsNoNsg = allSubnets.filter((s) => !s.nsg_id && !PLATFORM_SUBNETS.has(s.name));
  const unassocPIPs  = allPIPs.filter((p) => !p.associated_resource_type);

  return (
    <div className="space-y-4">
      {/* ── Header bar ── */}
      <div className="glass flex items-center justify-between p-4">
        <div>
          <p className="label-caps text-navy-300 dark:text-navy-500">Network Inventory</p>
          <p className="mt-0.5 text-xs text-navy-400 dark:text-navy-400">
            {subs.length} subscription{subs.length !== 1 ? "s" : ""} · Tenant {topology.tenant_id.slice(0, 8)}…
            {jobDate && <span className="ml-2">· Discovered {new Date(jobDate).toLocaleString()}</span>}
          </p>
        </div>
        {/* Summary pills */}
        <div className="hidden flex-wrap justify-end gap-2 sm:flex">
          {[
            { label: "VNets", value: allVnets.length },
            { label: "Subnets", value: allSubnets.length },
            { label: "NSGs", value: allNsgs.length },
            { label: "LBs", value: allLbs.length },
            { label: "Gateways", value: allGws.length },
            { label: "PEs", value: allPEs.length },
          ].map((s) => (
            <span key={s.label} className="pill-teal">
              {s.value} {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* ── Subscriptions ── */}
      <InvCard title="Subscriptions" count={subs.length} table>
        <THead cols={["Subscription", "VNets", "NSGs", "Firewalls", "LBs", "Gateways", "PEs", "Status"]} />
        <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
          {subs.map((s) => (
            <tr key={s.subscription_id}>
              <td className="py-2 pr-4">
                <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">
                  {s.subscription_name ?? s.subscription_id}
                </p>
                <p className="font-mono text-xs text-navy-400 dark:text-navy-500">
                  {s.subscription_id.slice(0, 8)}…
                </p>
              </td>
              <Td>{s.vnets?.length ?? 0}</Td>
              <Td>{s.nsgs?.length ?? 0}</Td>
              <Td>{s.firewalls?.length ?? 0}</Td>
              <Td>{s.load_balancers?.length ?? 0}</Td>
              <Td>{s.virtual_network_gateways?.length ?? 0}</Td>
              <Td>{s.private_endpoints?.length ?? 0}</Td>
              <td className="py-2 text-center">
                {s.discovery_blocked ? (
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 dark:bg-red-900/30 dark:text-red-400">Blocked</span>
                ) : (
                  <span className="pill-teal">OK</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </InvCard>

      {/* ── VNets ── */}
      {allVnets.length > 0 && (
        <InvCard title="Virtual Networks" count={allVnets.length} table>
          <THead cols={["Name", "Location", "Resource Group", "Address Space", "DNS Servers", "Subnets", "Peerings", "DDoS", "Encrypted"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allVnets.map((v) => (
              <tr key={v.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{v.name}</td>
                <Td>{v.location}</Td>
                <Mono>{v.resource_group}</Mono>
                <Mono>{v.address_space.join(", ")}</Mono>
                <td className="py-2 pr-3 font-mono text-xs text-navy-500 dark:text-navy-400">
                  {v.dns_servers?.length ? v.dns_servers.join(", ") : "Azure Default"}
                </td>
                <Td>{v.subnets.length}</Td>
                <Td>{v.peerings.length}</Td>
                <td className="py-2 text-center text-sm">
                  {v.ddos_protection_enabled ? <Ok /> : <Warn />}
                </td>
                <td className="py-2 text-center text-sm">
                  {v.encryption_enabled ? <Ok /> : <Dash />}
                </td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── Subnets + NSG coverage ── */}
      <InvCard
        title="Subnets & NSG Coverage"
        count={allSubnets.length}
        badge={subnetsNoNsg.length > 0 ? `${subnetsNoNsg.length} unprotected` : "All protected"}
        badgeVariant={subnetsNoNsg.length > 0 ? "warn" : "ok"}
        table
      >
        <THead cols={["Subnet", "VNet", "CIDR", "NSG", "Route Table", "NAT GW", "Delegation", "Svc Endpoints"]} />
        <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
          {allSubnets.map((s) => {
            const platform = PLATFORM_SUBNETS.has(s.name);
            const noNsg = !s.nsg_id && !platform;
            return (
              <tr key={s.id} className={noNsg ? "bg-amber-50/40 dark:bg-amber-900/10" : ""}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{s.name}</td>
                <Td>{s._vnet}</Td>
                <Mono>{s.address_prefix}</Mono>
                <td className="py-2 pr-3 text-xs">
                  {s.nsg_name ? (
                    <span className="font-mono text-teal-600 dark:text-teal-400">{s.nsg_name}</span>
                  ) : platform ? (
                    <Dash />
                  ) : (
                    <span className="font-semibold text-amber-600 dark:text-amber-400">None</span>
                  )}
                </td>
                <td className="py-2 pr-3 text-xs font-mono text-navy-500 dark:text-navy-400">
                  {s.route_table_name ?? <Dash />}
                </td>
                <td className="py-2 pr-3 text-center text-xs">
                  {s.nat_gateway_id ? <Ok /> : <Dash />}
                </td>
                <td className="py-2 pr-3 text-xs text-navy-500 dark:text-navy-400">
                  {s.delegation ?? "—"}
                </td>
                <td className="py-2 text-xs text-navy-500 dark:text-navy-400">
                  {s.service_endpoints?.length ? s.service_endpoints.join(", ") : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </InvCard>

      {/* ── NSG Rules ── */}
      {allNsgs.length > 0 && (
        <InvCard title="Network Security Groups" count={allNsgs.length}>
          <div className="space-y-4">
            {allNsgs.map((nsg) => (
              <details key={nsg.id} className="rounded-xl border border-navy-100/60 dark:border-navy-700/40">
                <summary className="flex cursor-pointer select-none items-center justify-between rounded-xl px-4 py-2.5 hover:bg-navy-50/40 dark:hover:bg-navy-800/30">
                  <div className="flex items-center gap-3">
                    <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">{nsg.name}</p>
                    <span className="font-mono text-xs text-navy-400 dark:text-navy-500">{nsg.resource_group}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="pill-teal">{nsg.security_rules.length} custom rules</span>
                    <span className="text-xs text-navy-400 dark:text-navy-500">
                      {nsg.associated_subnet_ids.length} subnets
                    </span>
                  </div>
                </summary>
                {nsg.security_rules.length > 0 && (
                  <div className="overflow-x-auto border-t border-navy-100/40 dark:border-navy-700/40">
                    <table className="w-full text-xs">
                      <THead cols={["Priority", "Direction", "Access", "Protocol", "Source", "Destination", "Port", "Description"]} />
                      <tbody className="divide-y divide-navy-50/80 dark:divide-navy-800/60">
                        {nsg.security_rules
                          .sort((a, b) => a.priority - b.priority)
                          .map((r) => (
                            <tr key={r.name} className={r.access === "Deny" ? "bg-red-50/30 dark:bg-red-900/10" : ""}>
                              <Td>{r.priority}</Td>
                              <td className="py-1.5 pr-3">
                                <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${r.direction === "Inbound" ? "bg-navy-100 text-navy-600 dark:bg-navy-700/60 dark:text-navy-300" : "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400"}`}>
                                  {r.direction}
                                </span>
                              </td>
                              <td className="py-1.5 pr-3">
                                <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${r.access === "Allow" ? "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300" : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"}`}>
                                  {r.access}
                                </span>
                              </td>
                              <Mono>{r.protocol}</Mono>
                              <Mono>{r.source_address_prefix ?? r.source_address_prefixes?.join(", ") ?? "*"}</Mono>
                              <Mono>{r.destination_address_prefix ?? r.destination_address_prefixes?.join(", ") ?? "*"}</Mono>
                              <Mono>{r.destination_port_range ?? r.destination_port_ranges?.join(", ") ?? "*"}</Mono>
                              <td className="py-1.5 text-navy-400 dark:text-navy-500">{r.description ?? "—"}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </details>
            ))}
          </div>
        </InvCard>
      )}

      {/* ── Route Tables ── */}
      {allRts.length > 0 && (
        <InvCard title="Route Tables" count={allRts.length}>
          <div className="space-y-3">
            {allRts.map((rt) => (
              <details key={rt.id} className="rounded-xl border border-navy-100/60 dark:border-navy-700/40">
                <summary className="flex cursor-pointer select-none items-center justify-between rounded-xl px-4 py-2.5 hover:bg-navy-50/40 dark:hover:bg-navy-800/30">
                  <div className="flex items-center gap-3">
                    <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">{rt.name}</p>
                    <span className="font-mono text-xs text-navy-400 dark:text-navy-500">{rt.resource_group}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="pill-teal">{rt.routes.length} routes</span>
                    <span className="text-xs text-navy-400 dark:text-navy-500">
                      BGP propagation: {rt.disable_bgp_route_propagation ? "disabled" : "enabled"}
                    </span>
                  </div>
                </summary>
                {rt.routes.length > 0 && (
                  <div className="overflow-x-auto border-t border-navy-100/40 dark:border-navy-700/40">
                    <table className="w-full text-xs">
                      <THead cols={["Route Name", "Address Prefix", "Next Hop Type", "Next Hop IP"]} />
                      <tbody className="divide-y divide-navy-50/80 dark:divide-navy-800/60">
                        {rt.routes.map((r) => (
                          <tr key={r.name}>
                            <td className="py-1.5 pr-3 font-semibold text-navy-700 dark:text-navy-200">{r.name}</td>
                            <Mono>{r.address_prefix}</Mono>
                            <td className="py-1.5 pr-3">
                              <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${r.next_hop_type === "Internet" ? "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400" : r.next_hop_type === "VirtualAppliance" ? "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300" : "bg-navy-50 text-navy-500 dark:bg-navy-700/40 dark:text-navy-300"}`}>
                                {r.next_hop_type}
                              </span>
                            </td>
                            <Mono>{r.next_hop_ip ?? "—"}</Mono>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </details>
            ))}
          </div>
        </InvCard>
      )}

      {/* ── Firewalls ── */}
      {allFirewalls.length > 0 && (
        <InvCard title="Azure Firewalls" count={allFirewalls.length} table>
          <THead cols={["Name", "Location", "Resource Group", "SKU", "Threat Intel", "Public IPs", "Zones"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allFirewalls.map((f) => (
              <tr key={f.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{f.name}</td>
                <Td>{f.location}</Td>
                <Mono>{f.resource_group}</Mono>
                <td className="py-2 pr-3">
                  <span className="rounded bg-navy-100 px-1.5 py-0.5 text-xs font-semibold text-navy-600 dark:bg-navy-700/60 dark:text-navy-300">{f.sku_tier}</span>
                </td>
                <td className="py-2 pr-3">
                  <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${f.threat_intel_mode === "Deny" ? "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300" : "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"}`}>
                    {f.threat_intel_mode}
                  </span>
                </td>
                <Td>{f.public_ip_ids?.length ?? 0}</Td>
                <Td>{f.zones?.join(", ") || "—"}</Td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── Application Gateways ── */}
      {allAppGws.length > 0 && (
        <InvCard title="Application Gateways" count={allAppGws.length} table>
          <THead cols={["Name", "Location", "Resource Group", "SKU", "WAF", "WAF Mode", "Rule Set", "Zones"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allAppGws.map((a) => (
              <tr key={a.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{a.name}</td>
                <Td>{a.location}</Td>
                <Mono>{a.resource_group}</Mono>
                <Mono>{a.sku_name}</Mono>
                <td className="py-2 pr-3 text-center">
                  {a.waf_enabled ? <Ok /> : <Warn label="Disabled" />}
                </td>
                <Td>{a.waf_mode ?? "—"}</Td>
                <Td>{a.waf_rule_set_type && a.waf_rule_set_version ? `${a.waf_rule_set_type} ${a.waf_rule_set_version}` : "—"}</Td>
                <Td>{a.zones?.join(", ") || "—"}</Td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── Load Balancers ── */}
      {allLbs.length > 0 && (
        <InvCard title="Load Balancers" count={allLbs.length}>
          <div className="space-y-3">
            {allLbs.map((lb) => (
              <details key={lb.id} className="rounded-xl border border-navy-100/60 dark:border-navy-700/40">
                <summary className="flex cursor-pointer select-none items-center justify-between rounded-xl px-4 py-2.5 hover:bg-navy-50/40 dark:hover:bg-navy-800/30">
                  <div className="flex items-center gap-3">
                    <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">{lb.name}</p>
                    <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${lb.lb_type === "Internal" ? "bg-navy-100 text-navy-600 dark:bg-navy-700/60 dark:text-navy-300" : "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"}`}>
                      {lb.lb_type}
                    </span>
                    <span className="text-xs text-navy-400 dark:text-navy-500">{lb.sku_name} · {lb.location}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="pill-teal">{lb.lb_rules?.length ?? 0} rules</span>
                    <span className="text-xs text-navy-400 dark:text-navy-500">
                      zones: {lb.zones?.join(",") || "—"}
                    </span>
                  </div>
                </summary>
                {(lb.lb_rules?.length ?? 0) > 0 && (
                  <div className="overflow-x-auto border-t border-navy-100/40 dark:border-navy-700/40">
                    <table className="w-full text-xs">
                      <THead cols={["Rule", "Protocol", "Frontend Port", "Backend Port"]} />
                      <tbody className="divide-y divide-navy-50/80 dark:divide-navy-800/60">
                        {lb.lb_rules?.map((r) => (
                          <tr key={r.name}>
                            <td className="py-1.5 pr-3 font-semibold text-navy-700 dark:text-navy-200">{r.name}</td>
                            <Mono>{r.protocol}</Mono>
                            <Td>{r.frontend_port}</Td>
                            <Td>{r.backend_port}</Td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </details>
            ))}
          </div>
        </InvCard>
      )}

      {/* ── VNet Gateways ── */}
      {allGws.length > 0 && (
        <InvCard title="VNet Gateways" count={allGws.length}>
          <div className="space-y-3">
            {allGws.map((gw) => (
              <details key={gw.id} className="rounded-xl border border-navy-100/60 dark:border-navy-700/40">
                <summary className="flex cursor-pointer select-none items-center justify-between rounded-xl px-4 py-2.5 hover:bg-navy-50/40 dark:hover:bg-navy-800/30">
                  <div className="flex items-center gap-3">
                    <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">{gw.name}</p>
                    <span className="rounded bg-navy-100 px-1.5 py-0.5 text-xs font-semibold text-navy-600 dark:bg-navy-700/60 dark:text-navy-300">{gw.gateway_type}</span>
                    <span className="text-xs text-navy-400 dark:text-navy-500">{gw.sku_name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-navy-400 dark:text-navy-500">
                      ActiveActive: {gw.active_active ? "Yes" : "No"} · BGP: {gw.enable_bgp ? `Yes (ASN ${gw.bgp_asn})` : "No"}
                    </span>
                    <span className="pill-teal">{gw.connections?.length ?? 0} connections</span>
                  </div>
                </summary>
                {(gw.connections?.length ?? 0) > 0 && (
                  <div className="overflow-x-auto border-t border-navy-100/40 dark:border-navy-700/40">
                    <table className="w-full text-xs">
                      <THead cols={["Connection", "Type", "Status", "BGP"]} />
                      <tbody className="divide-y divide-navy-50/80 dark:divide-navy-800/60">
                        {gw.connections?.map((c) => (
                          <tr key={c.name}>
                            <td className="py-1.5 pr-3 font-semibold text-navy-700 dark:text-navy-200">{c.name}</td>
                            <Mono>{c.connection_type}</Mono>
                            <td className="py-1.5 pr-3">
                              <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${c.connection_status === "Connected" ? "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300" : "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"}`}>
                                {c.connection_status}
                              </span>
                            </td>
                            <td className="py-1.5 text-xs">{c.enable_bgp ? <Ok /> : <Dash />}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </details>
            ))}
          </div>
        </InvCard>
      )}

      {/* ── Private Endpoints ── */}
      {allPEs.length > 0 && (
        <InvCard title="Private Endpoints" count={allPEs.length} table>
          <THead cols={["Name", "Location", "Resource Group", "Subnet", "Services", "DNS Configs"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allPEs.map((pe) => (
              <tr key={pe.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{pe.name}</td>
                <Td>{pe.location}</Td>
                <Mono>{pe.resource_group}</Mono>
                <Mono>{pe.subnet_id?.split("/").slice(-1)[0] ?? "—"}</Mono>
                <td className="py-2 pr-3 text-xs text-navy-500 dark:text-navy-400">
                  {pe.service_connections?.map((sc) => {
                    const svcName = sc.private_link_service_id?.split("/").slice(-1)[0] ?? "?";
                    return (
                      <span key={sc.connection_name} className={`mr-1 rounded px-1.5 py-0.5 font-semibold ${sc.connection_state === "Approved" ? "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300" : "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"}`}>
                        {svcName} ({sc.group_ids?.join(",") || "?"})
                      </span>
                    );
                  })}
                </td>
                <Td>{pe.custom_dns_configs?.join(", ") || "—"}</Td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── Public IPs ── */}
      {allPIPs.length > 0 && (
        <InvCard
          title="Public IP Addresses"
          count={allPIPs.length}
          badge={unassocPIPs.length > 0 ? `${unassocPIPs.length} unassociated` : undefined}
          badgeVariant="warn"
          table
        >
          <THead cols={["Name", "IP Address", "SKU", "Allocation", "Version", "Associated To", "Zones"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allPIPs.map((pip) => (
              <tr key={pip.id} className={!pip.associated_resource_type ? "bg-amber-50/30 dark:bg-amber-900/10" : ""}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{pip.name}</td>
                <Mono>{pip.ip_address ?? "dynamic"}</Mono>
                <Td>{pip.sku_name}</Td>
                <Td>{pip.allocation_method}</Td>
                <Td>{pip.ip_version}</Td>
                <td className="py-2 pr-3 text-xs text-navy-500 dark:text-navy-400">
                  {pip.associated_resource_type ?? <span className="font-semibold text-amber-600 dark:text-amber-400">Unassociated</span>}
                </td>
                <Td>{pip.zones?.join(", ") || "—"}</Td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── NAT Gateways ── */}
      {allNats.length > 0 && (
        <InvCard title="NAT Gateways" count={allNats.length} table>
          <THead cols={["Name", "Location", "Resource Group", "Public IPs", "Subnets", "Timeout (min)", "Zones"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allNats.map((ng) => (
              <tr key={ng.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{ng.name}</td>
                <Td>{ng.location}</Td>
                <Mono>{ng.resource_group}</Mono>
                <Td>{ng.public_ip_ids?.length ?? 0}</Td>
                <Td>{ng.associated_subnet_ids?.length ?? 0}</Td>
                <Td>{ng.idle_timeout_minutes}</Td>
                <Td>{ng.zones?.join(", ") || "—"}</Td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── Bastion Hosts ── */}
      {allBastions.length > 0 && (
        <InvCard title="Bastion Hosts" count={allBastions.length} table>
          <THead cols={["Name", "Location", "Resource Group", "SKU", "Tunneling", "Shareable Link"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allBastions.map((b) => (
              <tr key={b.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{b.name}</td>
                <Td>{b.location}</Td>
                <Mono>{b.resource_group}</Mono>
                <td className="py-2 pr-3">
                  <span className="rounded bg-navy-100 px-1.5 py-0.5 text-xs font-semibold text-navy-600 dark:bg-navy-700/60 dark:text-navy-300">{b.sku_name}</span>
                </td>
                <td className="py-2 pr-3 text-center">{b.tunneling_enabled ? <Ok /> : <Dash />}</td>
                <td className="py-2 text-center">{b.shareable_link_enabled ? <Ok /> : <Dash />}</td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── Private DNS Zones ── */}
      {allDnsZones.length > 0 && (
        <InvCard title="Private DNS Zones" count={allDnsZones.length} table>
          <THead cols={["Zone Name", "Resource Group", "Records", "Linked VNets", "Auto-Registration"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allDnsZones.map((z) => (
              <tr key={z.id}>
                <td className="py-2 pr-3 font-mono text-xs font-semibold text-navy-700 dark:text-navy-100">{z.name}</td>
                <Mono>{z.resource_group}</Mono>
                <Td>{z.record_count}</Td>
                <Td>{z.linked_vnet_ids?.length ?? 0}</Td>
                <td className="py-2 text-center">{z.auto_registration_enabled ? <Ok /> : <Dash />}</td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}

      {/* ── ExpressRoute Circuits ── */}
      {allERs.length > 0 && (
        <InvCard title="ExpressRoute Circuits" count={allERs.length} table>
          <THead cols={["Name", "Provider", "Peering Location", "Bandwidth", "SKU", "Peering Types", "Global Reach", "State"]} />
          <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
            {allERs.map((er) => (
              <tr key={er.id}>
                <td className="py-2 pr-3 text-sm font-semibold text-navy-700 dark:text-navy-100">{er.name}</td>
                <Td>{er.service_provider ?? "—"}</Td>
                <Td>{er.peering_location ?? "—"}</Td>
                <Td>{er.bandwidth_mbps != null ? `${er.bandwidth_mbps} Mbps` : "—"}</Td>
                <td className="py-2 pr-3">
                  <span className="rounded bg-navy-100 px-1.5 py-0.5 text-xs font-semibold text-navy-600 dark:bg-navy-700/60 dark:text-navy-300">{er.sku_tier}</span>
                </td>
                <Td>{er.peering_types?.join(", ") || "—"}</Td>
                <td className="py-2 pr-3 text-center">{er.global_reach_enabled ? <Ok /> : <Dash />}</td>
                <td className="py-2">
                  <span className={`text-xs font-semibold ${er.circuit_provisioning_state === "Enabled" ? "text-teal-600 dark:text-teal-400" : "text-amber-600 dark:text-amber-400"}`}>
                    {er.circuit_provisioning_state}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </InvCard>
      )}
    </div>
  );
}

// ── Shared primitives ─────────────────────────────────────────────────────────

function InvCard({
  title,
  count,
  badge,
  badgeVariant = "ok",
  table = false,
  children,
}: {
  title: string;
  count: number;
  badge?: string;
  badgeVariant?: "ok" | "warn";
  table?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="glass p-5">
      <div className="mb-4 flex items-center gap-3">
        <p className="label-caps text-navy-300 dark:text-navy-500">{title}</p>
        <span className="pill-teal">{count}</span>
        {badge && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${badgeVariant === "warn" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" : "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"}`}>
            {badge}
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        {table ? <table className="min-w-full">{children}</table> : children}
      </div>
    </div>
  );
}

function THead({ cols }: { cols: string[] }) {
  return (
    <thead>
      <tr className="border-b border-navy-100/40 dark:border-navy-700/40">
        {cols.map((c) => (
          <th key={c} className="pb-2 pr-3 text-left text-xs font-semibold text-navy-400 last:pr-0 dark:text-navy-500">
            {c}
          </th>
        ))}
      </tr>
    </thead>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="py-2 pr-3 text-xs text-navy-500 last:pr-0 dark:text-navy-400">{children}</td>;
}

function Mono({ children }: { children: React.ReactNode }) {
  return <td className="py-2 pr-3 font-mono text-xs text-navy-600 last:pr-0 dark:text-navy-300">{children}</td>;
}

function Ok({ label = "✓" }: { label?: string }) {
  return <span className="font-semibold text-teal-600 dark:text-teal-400">{label}</span>;
}

function Warn({ label = "✗" }: { label?: string }) {
  return <span className="font-semibold text-amber-600 dark:text-amber-400">{label}</span>;
}

function Dash() {
  return <span className="text-navy-300 dark:text-navy-700">—</span>;
}
