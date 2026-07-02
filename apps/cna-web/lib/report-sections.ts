// ──────────────────────────────────────────────────────────────────────────────
// Section skeleton + data slicing for the sectioned Comprehensive Assessment.
// Each section declares a charter (what it must cover) and a slice() that
// returns ONLY the engagement data relevant to that section — the model never
// sees data it shouldn't ground on, and per-call context stays small.
// ──────────────────────────────────────────────────────────────────────────────

import { classifyTrafficDirection, type FindingLike } from "@/lib/derive-stat-masters";

export interface ReportFinding extends FindingLike {
  id: string;
  recommendation?: string | null;
  aiGenerated?: boolean;
}

export interface SectionInput {
  clientOrg: string;
  engagementName: string;
  findings: ReportFinding[];
  /** Merged multi-subscription topology JSON (raw string) */
  topologyJson?: string | null;
  /** Pre-rendered full topology summary (from openai.ts summarizeTopology) */
  topologySummary?: string | null;
  credentialsInfo?: Array<{
    label: string;
    platform: string;
    tenantId: string | null;
    subscriptionIds: string[];
  }>;
  documents?: { fileName: string; text: string }[];
}

export interface SectionSpec {
  id: string;
  number: number;
  title: string;
  /** What the section must cover — becomes charter bullets in the prompt. */
  charter: string[];
  maxCompletionTokens: number;
  /**
   * Return the data slice for this section, or null when the engagement has
   * no data for the domain (the orchestrator then emits a deterministic stub
   * instead of spending an AI call).
   */
  slice(input: SectionInput): string | null;
}

// ── Finding formatters ────────────────────────────────────────────────────────

const MAX_SLICE_CHARS = 40_000; // ~10k tokens ceiling per section context

function formatFindings(findings: ReportFinding[], heading: string): string | null {
  if (!findings.length) return null;
  const lines = [`=== ${heading} (${findings.length}) ===`];
  for (const f of findings) {
    lines.push(`Finding: ${f.title}`);
    lines.push(`  Severity: ${f.severity} | Category: ${f.category}`);
    if (f.region) lines.push(`  Region: ${f.region}`);
    if (f.resourceType) lines.push(`  Resource type: ${f.resourceType}`);
    if (typeof f.estCostImpact === "number" && f.estCostImpact > 0) {
      lines.push(`  Est. monthly cost impact: $${f.estCostImpact} [VERIFY]`);
    }
    if (f.description) lines.push(`  Description: ${f.description}`);
    if (f.recommendation) lines.push(`  Recommendation: ${f.recommendation}`);
  }
  return lines.join("\n").slice(0, MAX_SLICE_CHARS);
}

function byDirection(findings: ReportFinding[], dir: string): ReportFinding[] {
  return findings.filter((f) => classifyTrafficDirection(f) === dir);
}

function byPattern(findings: ReportFinding[], re: RegExp): ReportFinding[] {
  return findings.filter((f) => re.test(`${f.title} ${f.category} ${f.description ?? ""}`));
}

const ROUTING_RE = /\b(rout|udr|bgp|next.hop|expressroute|express route|vpn|peering|transit|black.?hole|prefix)\b/i;
const MONITORING_RE = /\b(log|monitor|observab|diagnostic|flow log|network watcher|alert|siem|audit|retention)\b/i;
const RESILIENCE_RE = /\b(resilien|availab|redundan|zone|sla|failover|single point|spof|health probe|active.active|ddos)\b/i;
const IDENTITY_RE = /\b(identity|rbac|role.based|privileg|bastion|jit|management plane|admin|credential|service principal|managed identity)\b/i;
const COST_RE = /\bcost|finops|optimi[sz]ation|spend|orphan|idle|unused|oversized\b/i;
const FRAMEWORK_RE = /\b(NIST\s?(SP\s?800-53)?[\s-]*[A-Z]{2}-\d+|CIS\s?(Azure|Controls?)?\s?v?\d+(\.\d+)*|ISO\s?27001|SOC\s?2|HIPAA|PCI[\s-]?DSS|Zero Trust|Well-Architected)\b/i;

// ── Topology extractors ───────────────────────────────────────────────────────
// Pure functions over the parsed topology JSON — each returns a compact text
// extract for one domain, mirroring the style of summarizeTopology().

type Topo = { subscriptions?: Array<Record<string, unknown>> };

function parseTopo(topologyJson?: string | null): Topo | null {
  if (!topologyJson) return null;
  try {
    return JSON.parse(topologyJson) as Topo;
  } catch {
    return null;
  }
}

function subName(sub: Record<string, unknown>): string {
  return String(sub.subscription_name ?? sub.subscription_id ?? "unknown");
}

function arr(sub: Record<string, unknown>, key: string): Array<Record<string, unknown>> {
  return (sub[key] as Array<Record<string, unknown>> | undefined) ?? [];
}

export function extractPerimeter(topologyJson?: string | null): string | null {
  const topo = parseTopo(topologyJson);
  if (!topo?.subscriptions?.length) return null;
  const lines = ["=== PERIMETER TOPOLOGY EXTRACT ==="];
  for (const sub of topo.subscriptions) {
    lines.push(`Subscription: ${subName(sub)}`);
    const fws = arr(sub, "firewalls");
    lines.push(fws.length ? `  Azure Firewalls (${fws.length}):` : "  Azure Firewalls: NONE DEPLOYED");
    for (const fw of fws) {
      lines.push(`    - ${fw.name} sku=${fw.sku_tier} threatIntel=${fw.threat_intel_mode} zones=${((fw.zones as string[]) ?? []).join(",") || "none"}`);
    }
    for (const agw of arr(sub, "application_gateways")) {
      lines.push(`  AppGW: ${agw.name} sku=${agw.sku_name} waf=${agw.waf_enabled} wafMode=${agw.waf_mode ?? "N/A"}`);
    }
    const pips = arr(sub, "public_ips");
    const unassoc = pips.filter((p) => !p.associated_resource_id);
    lines.push(`  Public IPs: ${pips.length} total, ${unassoc.length} unassociated`);
    for (const pip of pips) {
      lines.push(`    - ${pip.name} ${pip.ip_address ?? "dynamic"} assoc=${pip.associated_resource_type ?? "UNASSOCIATED"}`);
    }
    for (const gw of arr(sub, "virtual_network_gateways")) {
      lines.push(`  Gateway: ${gw.name} type=${gw.gateway_type} sku=${gw.sku_name} activeActive=${gw.active_active}`);
    }
    for (const lb of arr(sub, "load_balancers")) {
      lines.push(`  LB: ${lb.name} sku=${lb.sku_name} type=${lb.lb_type} zones=${((lb.zones as string[]) ?? []).join(",") || "none"}`);
    }
    for (const b of arr(sub, "bastion_hosts")) {
      lines.push(`  Bastion: ${b.name} sku=${b.sku_name}`);
    }
    for (const ng of arr(sub, "nat_gateways")) {
      lines.push(`  NAT GW: ${ng.name} pips=${(ng.public_ip_ids as string[] | undefined)?.length ?? 0}`);
    }
  }
  return lines.join("\n").slice(0, MAX_SLICE_CHARS);
}

export function extractSegmentation(topologyJson?: string | null): string | null {
  const topo = parseTopo(topologyJson);
  if (!topo?.subscriptions?.length) return null;
  const lines = ["=== SEGMENTATION TOPOLOGY EXTRACT ==="];
  for (const sub of topo.subscriptions) {
    lines.push(`Subscription: ${subName(sub)}`);
    for (const v of arr(sub, "vnets")) {
      lines.push(`  VNet ${v.name} [${((v.address_space as string[]) ?? []).join(", ")}]`);
      for (const s of (v.subnets as Array<Record<string, unknown>> | undefined) ?? []) {
        lines.push(`    Subnet ${s.name} ${s.address_prefix} NSG=${s.nsg_name ?? "NONE"} UDR=${s.route_table_name ?? "none"}`);
      }
      for (const p of (v.peerings as Array<Record<string, unknown>> | undefined) ?? []) {
        lines.push(`    Peering ${p.name} → ${p.remote_vnet_name ?? p.remote_vnet_id} state=${p.peering_state} gwTransit=${p.allow_gateway_transit} fwdTraffic=${p.allow_forwarded_traffic ?? "?"}`);
      }
    }
    for (const nsg of arr(sub, "nsgs")) {
      const rules = (nsg.security_rules as Array<Record<string, unknown>> | undefined) ?? [];
      lines.push(`  NSG ${nsg.name} subnets=${(nsg.associated_subnet_ids as string[] | undefined)?.length ?? 0} rules=${rules.length}`);
      for (const r of rules.slice(0, 15)) {
        const src = r.source_address_prefix ?? ((r.source_address_prefixes as string[]) ?? []).join(",");
        const dst = r.destination_address_prefix ?? ((r.destination_address_prefixes as string[]) ?? []).join(",");
        const port = r.destination_port_range ?? ((r.destination_port_ranges as string[]) ?? []).join(",");
        lines.push(`    [${r.priority}] ${r.direction} ${r.access} ${r.protocol} src=${src} dst=${dst} port=${port}`);
      }
      if (rules.length > 15) lines.push(`    ... ${rules.length - 15} more rules`);
    }
  }
  return lines.join("\n").slice(0, MAX_SLICE_CHARS);
}

export function extractRouting(topologyJson?: string | null): string | null {
  const topo = parseTopo(topologyJson);
  if (!topo?.subscriptions?.length) return null;
  const lines = ["=== ROUTING & CONNECTIVITY TOPOLOGY EXTRACT ==="];
  for (const sub of topo.subscriptions) {
    lines.push(`Subscription: ${subName(sub)}`);
    for (const rt of arr(sub, "route_tables")) {
      lines.push(`  Route Table ${rt.name} subnets=${(rt.associated_subnet_ids as string[] | undefined)?.length ?? 0} bgpPropagation=${!rt.disable_bgp_route_propagation}`);
      for (const r of (rt.routes as Array<Record<string, unknown>> | undefined) ?? []) {
        lines.push(`    ${r.name}: ${r.address_prefix} → ${r.next_hop_type}${r.next_hop_ip ? ` (${r.next_hop_ip})` : ""}`);
      }
    }
    for (const gw of arr(sub, "virtual_network_gateways")) {
      lines.push(`  Gateway ${gw.name} type=${gw.gateway_type} bgp=${gw.enable_bgp} asn=${gw.bgp_asn ?? "N/A"}`);
      for (const c of (gw.connections as Array<Record<string, unknown>> | undefined) ?? []) {
        lines.push(`    Conn ${c.name} type=${c.connection_type} status=${c.connection_status} bgp=${c.enable_bgp}`);
      }
    }
    for (const er of arr(sub, "express_route_circuits")) {
      lines.push(`  ExpressRoute ${er.name} provider=${er.service_provider ?? "?"} bw=${er.bandwidth_mbps ?? "?"}Mbps globalReach=${er.global_reach_enabled}`);
    }
    for (const z of arr(sub, "private_dns_zones")) {
      lines.push(`  Private DNS ${z.name} linkedVnets=${(z.linked_vnet_ids as string[] | undefined)?.length ?? 0} autoReg=${z.auto_registration_enabled}`);
    }
    for (const ng of arr(sub, "nat_gateways")) {
      lines.push(`  NAT GW ${ng.name} subnets=${(ng.associated_subnet_ids as string[] | undefined)?.length ?? 0}`);
    }
  }
  return lines.join("\n").slice(0, MAX_SLICE_CHARS);
}

export function extractManagementPlane(topologyJson?: string | null): string | null {
  const topo = parseTopo(topologyJson);
  if (!topo?.subscriptions?.length) return null;
  const lines = ["=== MANAGEMENT PLANE TOPOLOGY EXTRACT ==="];
  for (const sub of topo.subscriptions) {
    lines.push(`Subscription: ${subName(sub)}`);
    const bastions = arr(sub, "bastion_hosts");
    lines.push(bastions.length ? `  Bastion Hosts (${bastions.length}):` : "  Bastion Hosts: NONE DEPLOYED");
    for (const b of bastions) {
      lines.push(`    - ${b.name} sku=${b.sku_name} tunneling=${b.tunneling_enabled} shareableLink=${b.shareable_link_enabled}`);
    }
    for (const pe of arr(sub, "private_endpoints")) {
      lines.push(`  Private Endpoint ${pe.name} subnet=${String(pe.subnet_id ?? "").split("/").slice(-1)[0]}`);
    }
  }
  return lines.join("\n").slice(0, MAX_SLICE_CHARS);
}

export function extractResilience(topologyJson?: string | null): string | null {
  const topo = parseTopo(topologyJson);
  if (!topo?.subscriptions?.length) return null;
  const lines = ["=== RESILIENCE TOPOLOGY EXTRACT ==="];
  for (const sub of topo.subscriptions) {
    lines.push(`Subscription: ${subName(sub)}`);
    for (const lb of arr(sub, "load_balancers")) {
      lines.push(`  LB ${lb.name} sku=${lb.sku_name} probes=${(lb.probes as unknown[] | undefined)?.length ?? 0} zones=${((lb.zones as string[]) ?? []).join(",") || "NONE"}`);
    }
    for (const gw of arr(sub, "virtual_network_gateways")) {
      lines.push(`  Gateway ${gw.name} sku=${gw.sku_name} activeActive=${gw.active_active}`);
    }
    for (const fw of arr(sub, "firewalls")) {
      lines.push(`  Firewall ${fw.name} zones=${((fw.zones as string[]) ?? []).join(",") || "NONE"}`);
    }
    for (const v of arr(sub, "vnets")) {
      lines.push(`  VNet ${v.name} DDoS=${v.ddos_protection_enabled ? "enabled" : "NOT ENABLED"}`);
    }
  }
  return lines.join("\n").slice(0, MAX_SLICE_CHARS);
}

// ── Inventory counts (used by scope section and Appendix B) ──────────────────

const INVENTORY_KEYS: Array<[string, string]> = [
  ["vnets", "Virtual Networks"],
  ["nsgs", "Network Security Groups"],
  ["route_tables", "Route Tables"],
  ["virtual_network_gateways", "VNet Gateways"],
  ["load_balancers", "Load Balancers"],
  ["firewalls", "Azure Firewalls"],
  ["application_gateways", "Application Gateways"],
  ["public_ips", "Public IPs"],
  ["private_endpoints", "Private Endpoints"],
  ["nat_gateways", "NAT Gateways"],
  ["bastion_hosts", "Bastion Hosts"],
  ["express_route_circuits", "ExpressRoute Circuits"],
  ["private_dns_zones", "Private DNS Zones"],
];

export interface InventoryRow {
  subscription: string;
  counts: Array<{ label: string; count: number }>;
}

export function inventoryCounts(topologyJson?: string | null): InventoryRow[] {
  const topo = parseTopo(topologyJson);
  if (!topo?.subscriptions?.length) return [];
  return topo.subscriptions.map((sub) => ({
    subscription: subName(sub),
    counts: INVENTORY_KEYS.map(([key, label]) => ({ label, count: arr(sub, key).length })),
  }));
}

// ── Section skeleton ──────────────────────────────────────────────────────────

function severityBreakdown(findings: ReportFinding[]): string {
  const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];
  return order
    .map((s) => ({ s, n: findings.filter((f) => f.severity === s).length }))
    .filter((x) => x.n > 0)
    .map((x) => `${x.n} ${x.s}`)
    .join(", ");
}

export const COMPREHENSIVE_SECTIONS: SectionSpec[] = [
  // Section 1 (Executive Summary) is produced by the synthesis pass — not here.
  {
    id: "scope",
    number: 2,
    title: "Scope & Methodology",
    charter: [
      "Assessed cloud scope: tenants, subscriptions, and credentials used",
      "Discovery methodology: live Azure Resource Manager discovery plus rule-based and AI-assisted analysis",
      "Documents reviewed and their role in the assessment",
      "Explicit statement of what was NOT assessed (data limitations, blocked subscriptions)",
    ],
    maxCompletionTokens: 3000,
    slice(input) {
      const lines = ["=== SCOPE DATA ==="];
      for (const c of input.credentialsInfo ?? []) {
        lines.push(`Credential: [${c.platform}] ${c.label} tenant=${c.tenantId ?? "N/A"} subscriptions=${c.subscriptionIds.join(", ") || "all accessible"}`);
      }
      lines.push(`Total findings: ${input.findings.length} (${severityBreakdown(input.findings)})`);
      lines.push(`Live-discovery findings: ${input.findings.filter((f) => !f.aiGenerated).length}; AI-analysis findings: ${input.findings.filter((f) => f.aiGenerated).length}`);
      const inv = inventoryCounts(input.topologyJson);
      for (const row of inv) {
        lines.push(`Subscription "${row.subscription}": ${row.counts.filter((c) => c.count > 0).map((c) => `${c.count} ${c.label}`).join(", ")}`);
      }
      if (input.documents?.length) {
        lines.push(`Documents reviewed: ${input.documents.map((d) => d.fileName).join("; ")}`);
      }
      return lines.join("\n");
    },
  },
  {
    id: "architecture",
    number: 3,
    title: "Architecture & Topology Analysis",
    charter: [
      "Describe the discovered network architecture: hub/spoke or flat, address space plan, regions",
      "Traffic flow narrative: how north-south and east-west traffic actually moves today",
      "Dependency mapping: shared services, transit paths, single points of failure at the architecture level",
      "An ASCII/Unicode logical topology diagram of the discovered environment",
      "Architecture-level observations that individual findings do not capture",
    ],
    maxCompletionTokens: 6000,
    slice(input) {
      return input.topologySummary ?? null;
    },
  },
  {
    id: "perimeter",
    number: 4,
    title: "Perimeter Security (North–South)",
    charter: [
      "Internet exposure surface: public IPs, exposed services, ingress paths",
      "Perimeter inspection posture: firewall coverage, WAF, DDoS protection",
      "Egress control: outbound paths, NAT, forced tunneling",
      "Each relevant finding analyzed in depth with concrete Azure remediation steps",
    ],
    maxCompletionTokens: 6000,
    slice(input) {
      const f = formatFindings(byDirection(input.findings, "north_south"), "NORTH-SOUTH FINDINGS");
      const t = extractPerimeter(input.topologyJson);
      if (!f && !t) return null;
      return [f, t].filter(Boolean).join("\n\n");
    },
  },
  {
    id: "segmentation",
    number: 5,
    title: "Network Segmentation (East–West)",
    charter: [
      "Segmentation model: VNet/subnet isolation, NSG coverage and rule quality",
      "Lateral movement paths: peering mesh, permissive intra-VNet rules, missing micro-segmentation",
      "Zero Trust alignment of the current segmentation design",
      "Each relevant finding analyzed in depth with concrete Azure remediation steps",
    ],
    maxCompletionTokens: 6000,
    slice(input) {
      const f = formatFindings(byDirection(input.findings, "east_west"), "EAST-WEST FINDINGS");
      const t = extractSegmentation(input.topologyJson);
      if (!f && !t) return null;
      return [f, t].filter(Boolean).join("\n\n");
    },
  },
  {
    id: "routing",
    number: 6,
    title: "Routing & Connectivity",
    charter: [
      "UDR posture: routes overriding system routing, next-hop safety, inspection bypass risk",
      "Hybrid connectivity: ExpressRoute/VPN design, BGP scope, redundancy",
      "DNS architecture: private zones, resolution paths, auto-registration",
      "Each relevant finding analyzed in depth with concrete Azure remediation steps",
    ],
    maxCompletionTokens: 5000,
    slice(input) {
      const f = formatFindings(byPattern(input.findings, ROUTING_RE), "ROUTING FINDINGS");
      const t = extractRouting(input.topologyJson);
      if (!f && !t) return null;
      return [f, t].filter(Boolean).join("\n\n");
    },
  },
  {
    id: "management",
    number: 7,
    title: "Identity & Management Plane",
    charter: [
      "Administrative access paths: Bastion coverage, exposed management ports, JIT",
      "Network-plane RBAC and privileged access observations",
      "Private endpoint adoption for management-plane traffic",
      "Each relevant finding analyzed in depth with concrete Azure remediation steps",
    ],
    maxCompletionTokens: 5000,
    slice(input) {
      const mgmt = new Set(byDirection(input.findings, "management").map((f) => f.title));
      const idFindings = input.findings.filter(
        (f) => mgmt.has(f.title) || IDENTITY_RE.test(`${f.title} ${f.category} ${f.description ?? ""}`),
      );
      const f = formatFindings(idFindings, "IDENTITY & MANAGEMENT FINDINGS");
      const t = extractManagementPlane(input.topologyJson);
      if (!f && !t) return null;
      return [f, t].filter(Boolean).join("\n\n");
    },
  },
  {
    id: "observability",
    number: 8,
    title: "Logging, Monitoring & Observability",
    charter: [
      "Flow log / Network Watcher / diagnostic settings coverage",
      "Detection posture: what malicious activity would currently be visible vs invisible",
      "Log centralization and retention observations",
      "Each relevant finding analyzed in depth with concrete Azure remediation steps",
    ],
    maxCompletionTokens: 4000,
    slice(input) {
      return formatFindings(byPattern(input.findings, MONITORING_RE), "OBSERVABILITY FINDINGS");
    },
  },
  {
    id: "resilience",
    number: 9,
    title: "Resilience & Availability",
    charter: [
      "Zone redundancy posture across gateways, firewalls, and load balancers",
      "Failure-mode analysis: what breaks in a zone or region outage",
      "Health probe coverage and failover behavior",
      "Each relevant finding analyzed in depth with concrete Azure remediation steps",
    ],
    maxCompletionTokens: 4000,
    slice(input) {
      const f = formatFindings(byPattern(input.findings, RESILIENCE_RE), "RESILIENCE FINDINGS");
      const t = extractResilience(input.topologyJson);
      if (!f && !t) return null;
      return [f, t].filter(Boolean).join("\n\n");
    },
  },
  {
    id: "finops",
    number: 10,
    title: "FinOps & Cost Optimization",
    charter: [
      "Network cost-waste findings: orphaned public IPs, idle gateways, oversized SKUs",
      "Estimated monthly savings, each figure marked [VERIFY] (static-price approximations)",
      "Cost-risk tradeoffs: where saving money would weaken the security posture — and where it wouldn't",
    ],
    maxCompletionTokens: 4000,
    slice(input) {
      const costFindings = input.findings.filter(
        (f) =>
          (typeof f.estCostImpact === "number" && f.estCostImpact > 0) ||
          COST_RE.test(`${f.title} ${f.category}`),
      );
      return formatFindings(costFindings, "COST FINDINGS");
    },
  },
  {
    id: "compliance",
    number: 11,
    title: "Compliance Framework Mapping",
    charter: [
      "Map findings to framework controls referenced in the data (NIST SP 800-53, CIS Azure, Well-Architected, Zero Trust)",
      "Gap register table: control, requirement, current state, gap",
      "Audit-readiness narrative: what an assessor would flag first",
      "Only cite control IDs that appear in the finding data — do not invent mappings",
    ],
    maxCompletionTokens: 4000,
    slice(input) {
      if (!input.findings.length) return null;
      const lines = ["=== ALL FINDINGS (condensed for framework mapping) ==="];
      for (const f of input.findings) {
        const text = `${f.title} ${f.description ?? ""} ${f.recommendation ?? ""}`;
        const frameworks = text.match(new RegExp(FRAMEWORK_RE.source, "gi"));
        lines.push(`- [${f.severity}] ${f.title} (${f.category})${frameworks?.length ? ` — frameworks: ${[...new Set(frameworks)].join(", ")}` : ""}`);
      }
      return lines.join("\n").slice(0, MAX_SLICE_CHARS);
    },
  },
  {
    id: "remediation",
    number: 12,
    title: "Prioritized Remediation Roadmap",
    charter: [
      "Prioritize every finding by risk (severity, exploitability, blast radius) vs effort",
      "30/60/90-day phased roadmap with concrete tasks",
      "Dependencies between remediation tasks",
      "Validation step for each phase (how the client proves the fix landed)",
    ],
    maxCompletionTokens: 6000,
    slice(input) {
      if (!input.findings.length) return null;
      const lines = [`=== ALL FINDINGS FOR PRIORITIZATION (${input.findings.length}) ===`];
      for (const f of input.findings) {
        lines.push(`- [${f.severity}] ${f.title} (${f.category})`);
        if (f.recommendation) lines.push(`  Recommendation: ${f.recommendation}`);
        if (typeof f.estCostImpact === "number" && f.estCostImpact > 0) {
          lines.push(`  Est. monthly cost impact: $${f.estCostImpact} [VERIFY]`);
        }
      }
      return lines.join("\n").slice(0, MAX_SLICE_CHARS);
    },
  },
];

// ── Abbreviations glossary (Appendix D — deterministic) ───────────────────────

export const ABBREVIATIONS: Array<[string, string]> = [
  ["ACL", "Access control list"],
  ["AGW", "Application Gateway"],
  ["ARM", "Azure Resource Manager"],
  ["ASN", "Autonomous system number"],
  ["BGP", "Border Gateway Protocol"],
  ["CIS", "Center for Internet Security"],
  ["DDoS", "Distributed denial of service"],
  ["DNS", "Domain Name System"],
  ["ER", "ExpressRoute"],
  ["JIT", "Just-in-time (VM access)"],
  ["LB", "Load balancer"],
  ["NAT", "Network address translation"],
  ["NIST", "National Institute of Standards and Technology"],
  ["NSG", "Network security group"],
  ["NVA", "Network virtual appliance"],
  ["PE", "Private endpoint"],
  ["PIP", "Public IP address"],
  ["RBAC", "Role-based access control"],
  ["SKU", "Stock-keeping unit (service tier)"],
  ["SLA", "Service level agreement"],
  ["SPOF", "Single point of failure"],
  ["UDR", "User-defined route"],
  ["VNet", "Virtual network"],
  ["VPN", "Virtual private network"],
  ["WAF", "Web application firewall"],
];
