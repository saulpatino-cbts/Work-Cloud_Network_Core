import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

// ── Topology shape (subset we render) ────────────────────────────────────────

interface Subnet {
  id: string;
  name: string;
  address_prefix: string;
  nsg_id: string | null;
  route_table_id: string | null;
  service_endpoints: string[];
  delegation: string | null;
}

interface Peering {
  name: string;
  remote_vnet_name: string | null;
  remote_subscription_id: string;
  peering_state: string;
  allow_gateway_transit: boolean;
  use_remote_gateways: boolean;
}

interface VNet {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  address_space: string[];
  subnets: Subnet[];
  peerings: Peering[];
  ddos_protection_enabled: boolean;
  tags: Record<string, string>;
}

interface Firewall {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_tier: string;
  threat_intel_mode: string;
  public_ip_ids: string[];
}

interface AppGateway {
  id: string;
  name: string;
  location: string;
  resource_group: string;
  sku_name: string;
  waf_enabled: boolean;
}

interface PrivateDnsZone {
  id: string;
  name: string;
  resource_group: string;
  linked_vnet_ids: string[];
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
}

interface Subscription {
  subscription_id: string;
  subscription_name: string | null;
  discovery_blocked: boolean;
  block_reason: string | null;
  vnets: VNet[];
  firewalls: Firewall[];
  application_gateways: AppGateway[];
  private_dns_zones: PrivateDnsZone[];
  express_route_circuits: ExpressRoute[];
}

interface Topology {
  tenant_id: string;
  subscriptions: Subscription[];
}

function parseTopology(json: string): Topology | null {
  try {
    return JSON.parse(json) as Topology;
  } catch {
    return null;
  }
}

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

  let topologyJson: string | null = null;
  let jobDate: Date | null = null;
  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { topologyJson: true, completedAt: true },
    });
    topologyJson = job?.topologyJson ?? null;
    jobDate = job?.completedAt ?? null;
  } catch {
    // migration pending
  }

  if (!topologyJson) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-10 text-center">
        <p className="text-sm font-medium text-gray-500">No inventory data yet.</p>
        <p className="mt-1 text-xs text-gray-400">
          Run discovery on the{" "}
          <Link href={`/engagements/${id}/connections`} className="text-blue-600 hover:underline">
            Connections tab
          </Link>{" "}
          to populate the network inventory.
        </p>
      </div>
    );
  }

  const topology = parseTopology(topologyJson);
  if (!topology) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
        <p className="text-sm text-red-700">Failed to parse topology data.</p>
      </div>
    );
  }

  // ── Flatten all-subscription data ──────────────────────────────────────────
  const allVnets = topology.subscriptions.flatMap((s) =>
    s.vnets.map((v) => ({ ...v, sub_name: s.subscription_name ?? s.subscription_id })),
  );
  const allSubnets = allVnets.flatMap((v) =>
    v.subnets.map((s) => ({
      ...s,
      vnet_name: v.name,
      vnet_location: v.location,
      sub_name: v.sub_name,
    })),
  );
  const allFirewalls = topology.subscriptions.flatMap((s) =>
    s.firewalls.map((f) => ({ ...f, sub_name: s.subscription_name ?? s.subscription_id })),
  );
  const allAppGws = topology.subscriptions.flatMap((s) =>
    s.application_gateways.map((a) => ({
      ...a,
      sub_name: s.subscription_name ?? s.subscription_id,
    })),
  );
  const allDnsZones = topology.subscriptions.flatMap((s) =>
    s.private_dns_zones.map((z) => ({
      ...z,
      sub_name: s.subscription_name ?? s.subscription_id,
    })),
  );
  const allExpressRoutes = topology.subscriptions.flatMap((s) =>
    s.express_route_circuits.map((e) => ({
      ...e,
      sub_name: s.subscription_name ?? s.subscription_id,
    })),
  );

  // Collect all address prefixes (IPs/CIDRs used)
  const allCidrs = [
    ...allVnets.flatMap((v) => v.address_space.map((cidr) => ({ cidr, source: `VNet: ${v.name}`, sub: v.sub_name }))),
    ...allSubnets.map((s) => ({ cidr: s.address_prefix, source: `Subnet: ${s.name} (${s.vnet_name})`, sub: s.sub_name })),
  ].sort((a, b) => a.cidr.localeCompare(b.cidr));

  // NSG coverage
  const subnetsNoNsg = allSubnets.filter(
    (s) => !s.nsg_id && !["GatewaySubnet", "AzureBastionSubnet", "AzureFirewallSubnet", "AzureFirewallManagementSubnet", "RouteServerSubnet"].includes(s.name),
  );
  const subnetsWithNsg = allSubnets.filter((s) => !!s.nsg_id);

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Network Inventory
          </h2>
          <p className="text-sm text-gray-500">
            {topology.subscriptions.length} subscription(s) · Tenant:{" "}
            {topology.tenant_id.slice(0, 8)}…
            {jobDate && (
              <span className="ml-2 text-gray-400">
                · Discovered {new Date(jobDate).toLocaleString()}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* ── Subscription overview ── */}
      <SectionCard title="Subscriptions" count={topology.subscriptions.length}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
              <th className="pb-2 text-left">Subscription</th>
              <th className="pb-2 text-center">VNets</th>
              <th className="pb-2 text-center">Firewalls</th>
              <th className="pb-2 text-center">App Gateways</th>
              <th className="pb-2 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {topology.subscriptions.map((s) => (
              <tr key={s.subscription_id} className="text-sm">
                <td className="py-2 font-medium text-gray-900">
                  {s.subscription_name ?? s.subscription_id}
                  <span className="ml-2 font-mono text-xs text-gray-400">
                    {s.subscription_id.slice(0, 8)}…
                  </span>
                </td>
                <td className="py-2 text-center">{s.vnets.length}</td>
                <td className="py-2 text-center">{s.firewalls.length}</td>
                <td className="py-2 text-center">{s.application_gateways.length}</td>
                <td className="py-2 text-center">
                  {s.discovery_blocked ? (
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">
                      Blocked
                    </span>
                  ) : (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">
                      OK
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      {/* ── VNets ── */}
      {allVnets.length > 0 && (
        <SectionCard title="Virtual Networks (VNets)" count={allVnets.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <th className="pb-2 text-left">Name</th>
                <th className="pb-2 text-left">Location</th>
                <th className="pb-2 text-left">Resource Group</th>
                <th className="pb-2 text-left">Address Space</th>
                <th className="pb-2 text-center">Subnets</th>
                <th className="pb-2 text-center">Peerings</th>
                <th className="pb-2 text-center">DDoS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allVnets.map((v) => (
                <tr key={v.id}>
                  <td className="py-2 font-medium text-gray-900">{v.name}</td>
                  <td className="py-2 text-gray-500">{v.location}</td>
                  <td className="py-2 font-mono text-xs text-gray-500">
                    {v.resource_group}
                  </td>
                  <td className="py-2 font-mono text-xs text-gray-700">
                    {v.address_space.join(", ")}
                  </td>
                  <td className="py-2 text-center">{v.subnets.length}</td>
                  <td className="py-2 text-center">{v.peerings.length}</td>
                  <td className="py-2 text-center">
                    {v.ddos_protection_enabled ? (
                      <span className="text-green-600">✓</span>
                    ) : (
                      <span className="text-red-500">✗</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── NSG coverage ── */}
      <SectionCard
        title="NSG Coverage"
        count={allSubnets.length}
        badge={
          subnetsNoNsg.length > 0
            ? `${subnetsNoNsg.length} unprotected`
            : "All protected"
        }
        badgeColor={subnetsNoNsg.length > 0 ? "orange" : "green"}
      >
        <div className="mb-3 flex gap-4 text-sm">
          <span className="text-green-700">
            ✓ {subnetsWithNsg.length} subnets with NSG
          </span>
          <span className={subnetsNoNsg.length > 0 ? "text-orange-700" : "text-gray-400"}>
            ✗ {subnetsNoNsg.length} subnets without NSG
          </span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
              <th className="pb-2 text-left">Subnet</th>
              <th className="pb-2 text-left">VNet</th>
              <th className="pb-2 text-left">CIDR</th>
              <th className="pb-2 text-left">Delegation</th>
              <th className="pb-2 text-center">NSG</th>
              <th className="pb-2 text-center">Route Table</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {allSubnets.map((s) => (
              <tr key={s.id} className={!s.nsg_id && !["GatewaySubnet", "AzureBastionSubnet", "AzureFirewallSubnet", "AzureFirewallManagementSubnet", "RouteServerSubnet"].includes(s.name) ? "bg-orange-50" : ""}>
                <td className="py-2 font-medium text-gray-900">{s.name}</td>
                <td className="py-2 text-gray-500">{s.vnet_name}</td>
                <td className="py-2 font-mono text-xs text-gray-700">
                  {s.address_prefix}
                </td>
                <td className="py-2 text-xs text-gray-400">
                  {s.delegation ?? "—"}
                </td>
                <td className="py-2 text-center text-xs">
                  {s.nsg_id ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
                <td className="py-2 text-center text-xs">
                  {s.route_table_id ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      {/* ── IP / CIDR inventory ── */}
      {allCidrs.length > 0 && (
        <SectionCard title="IP & CIDR Inventory" count={allCidrs.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <th className="pb-2 text-left">CIDR / Prefix</th>
                <th className="pb-2 text-left">Resource</th>
                <th className="pb-2 text-left">Subscription</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allCidrs.map((c, i) => (
                <tr key={i}>
                  <td className="py-2 font-mono text-xs font-semibold text-gray-900">
                    {c.cidr}
                  </td>
                  <td className="py-2 text-xs text-gray-600">{c.source}</td>
                  <td className="py-2 text-xs text-gray-400">{c.sub}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── Firewalls ── */}
      {allFirewalls.length > 0 && (
        <SectionCard title="Azure Firewalls" count={allFirewalls.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <th className="pb-2 text-left">Name</th>
                <th className="pb-2 text-left">Location</th>
                <th className="pb-2 text-left">Resource Group</th>
                <th className="pb-2 text-center">SKU</th>
                <th className="pb-2 text-center">Threat Intel</th>
                <th className="pb-2 text-center">Public IPs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allFirewalls.map((f) => (
                <tr key={f.id}>
                  <td className="py-2 font-medium text-gray-900">{f.name}</td>
                  <td className="py-2 text-gray-500">{f.location}</td>
                  <td className="py-2 font-mono text-xs text-gray-500">
                    {f.resource_group}
                  </td>
                  <td className="py-2 text-center">
                    <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
                      {f.sku_tier}
                    </span>
                  </td>
                  <td className="py-2 text-center">
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                        f.threat_intel_mode === "Deny"
                          ? "bg-green-100 text-green-700"
                          : "bg-orange-100 text-orange-700"
                      }`}
                    >
                      {f.threat_intel_mode}
                    </span>
                  </td>
                  <td className="py-2 text-center text-xs text-gray-500">
                    {f.public_ip_ids.length}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── Application Gateways ── */}
      {allAppGws.length > 0 && (
        <SectionCard title="Application Gateways" count={allAppGws.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <th className="pb-2 text-left">Name</th>
                <th className="pb-2 text-left">Location</th>
                <th className="pb-2 text-left">Resource Group</th>
                <th className="pb-2 text-center">SKU</th>
                <th className="pb-2 text-center">WAF</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allAppGws.map((a) => (
                <tr key={a.id}>
                  <td className="py-2 font-medium text-gray-900">{a.name}</td>
                  <td className="py-2 text-gray-500">{a.location}</td>
                  <td className="py-2 font-mono text-xs text-gray-500">
                    {a.resource_group}
                  </td>
                  <td className="py-2 text-center text-xs">{a.sku_name}</td>
                  <td className="py-2 text-center">
                    {a.waf_enabled ? (
                      <span className="text-green-600">✓ Enabled</span>
                    ) : (
                      <span className="text-red-500">✗ Disabled</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── Private DNS Zones ── */}
      {allDnsZones.length > 0 && (
        <SectionCard title="Private DNS Zones" count={allDnsZones.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <th className="pb-2 text-left">Zone Name</th>
                <th className="pb-2 text-left">Resource Group</th>
                <th className="pb-2 text-center">Records</th>
                <th className="pb-2 text-center">Linked VNets</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allDnsZones.map((z) => (
                <tr key={z.id}>
                  <td className="py-2 font-mono text-xs text-gray-900">
                    {z.name}
                  </td>
                  <td className="py-2 font-mono text-xs text-gray-500">
                    {z.resource_group}
                  </td>
                  <td className="py-2 text-center text-xs">{z.record_count}</td>
                  <td className="py-2 text-center text-xs">
                    {z.linked_vnet_ids.length}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── ExpressRoute Circuits ── */}
      {allExpressRoutes.length > 0 && (
        <SectionCard
          title="ExpressRoute Circuits"
          count={allExpressRoutes.length}
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <th className="pb-2 text-left">Name</th>
                <th className="pb-2 text-left">Provider</th>
                <th className="pb-2 text-left">Peering Location</th>
                <th className="pb-2 text-center">Bandwidth</th>
                <th className="pb-2 text-center">SKU</th>
                <th className="pb-2 text-center">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allExpressRoutes.map((e) => (
                <tr key={e.id}>
                  <td className="py-2 font-medium text-gray-900">{e.name}</td>
                  <td className="py-2 text-xs text-gray-500">
                    {e.service_provider ?? "—"}
                  </td>
                  <td className="py-2 text-xs text-gray-500">
                    {e.peering_location ?? "—"}
                  </td>
                  <td className="py-2 text-center text-xs">
                    {e.bandwidth_mbps != null ? `${e.bandwidth_mbps} Mbps` : "—"}
                  </td>
                  <td className="py-2 text-center">
                    <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
                      {e.sku_tier}
                    </span>
                  </td>
                  <td className="py-2 text-center">
                    <span
                      className={`text-xs font-medium ${
                        e.circuit_provisioning_state === "Enabled"
                          ? "text-green-600"
                          : "text-yellow-600"
                      }`}
                    >
                      {e.circuit_provisioning_state}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}
    </div>
  );
}

function SectionCard({
  title,
  count,
  badge,
  badgeColor,
  children,
}: {
  title: string;
  count: number;
  badge?: string;
  badgeColor?: "green" | "orange" | "red";
  children: React.ReactNode;
}) {
  const badgeClasses = {
    green: "bg-green-100 text-green-700",
    orange: "bg-orange-100 text-orange-700",
    red: "bg-red-100 text-red-700",
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          {title}
        </h2>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">
          {count}
        </span>
        {badge && badgeColor && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${badgeClasses[badgeColor]}`}
          >
            {badge}
          </span>
        )}
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}
