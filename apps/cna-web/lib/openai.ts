import { AzureOpenAI } from "openai";
import { DefaultAzureCredential, getBearerTokenProvider } from "@azure/identity";
import type { FindingSeverity } from "@prisma/client";

export interface RawFinding {
  title: string;
  severity: FindingSeverity;
  category: string;
  description: string;
  recommendation: string;
  msLearnLinks?: string[];
  frameworkMapping?: string;
}

function getClient(): AzureOpenAI {
  const endpoint = process.env.AZURE_OPENAI_ENDPOINT;
  if (!endpoint) throw new Error("AZURE_OPENAI_ENDPOINT is not set");

  const credential = new DefaultAzureCredential();
  const azureADTokenProvider = getBearerTokenProvider(
    credential,
    "https://cognitiveservices.azure.com/.default",
  );

  return new AzureOpenAI({
    endpoint,
    azureADTokenProvider,
    apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? "2024-12-01-preview",
    deployment: process.env.AZURE_OPENAI_DEPLOYMENT ?? "gpt-4o",
  });
}

export type AnalysisFocus =
  | "general"
  | "zero_trust"
  | "compliance_nist"
  | "compliance_cis"
  | "well_architected"
  | "remediation_priority"
  | "traffic_flow"
  | "dependency_chains"
  | "interconnect"
  | "routing_decisions"
  | "resilience";

export const FOCUS_LABELS: Record<AnalysisFocus, string> = {
  general: "General Security",
  zero_trust: "Zero Trust",
  compliance_nist: "NIST SP 800-53",
  compliance_cis: "CIS Benchmark",
  well_architected: "Well-Architected",
  remediation_priority: "Quick Wins",
  traffic_flow: "Traffic Flow",
  dependency_chains: "Dependency Chains",
  interconnect: "Interconnect Behavior",
  routing_decisions: "Routing Decisions",
  resilience: "Resilience Assumptions",
};

const FOCUS_PROMPTS: Record<AnalysisFocus, string> = {
  general:
    "Identify all network security findings across all categories. Cover perimeter controls, segmentation, encryption in transit, identity-based access, monitoring gaps, and configuration drift.",
  zero_trust:
    "Focus on Zero Trust architecture gaps: micro-segmentation failures, implicit trust zones, lateral movement paths, missing identity-based access controls on network segments, absence of mTLS or service mesh, and network-layer authentication weaknesses.",
  compliance_nist:
    "Evaluate against NIST SP 800-53 Rev 5 network controls: SC-7 Boundary Protection, SC-8 Transmission Confidentiality, AC-4 Information Flow Enforcement, SI-3 Malicious Code Protection, AU-2 Event Logging. Map every finding to the exact NIST control identifier in frameworkMapping.",
  compliance_cis:
    "Evaluate against CIS Azure Foundations Benchmark v2.0 and CIS Controls v8. Map each finding to the exact CIS control/sub-control number in frameworkMapping. Focus on network hardening, NSG rules, public exposure, logging, and encryption.",
  well_architected:
    "Evaluate against the Azure Well-Architected Framework Security pillar. Focus on defense in depth, least privilege, network segmentation, encryption at rest/in transit, threat detection, and operational excellence for network resources.",
  remediation_priority:
    "Identify findings representing the highest-impact quick wins. Prioritize by: (1) exploitability in current state, (2) blast radius if compromised, (3) remediation complexity (flag anything fixable in under 1 day). Rank by combined risk score.",
  traffic_flow:
    "Analyze all observed and inferred network traffic flows. Identify: unrestricted east-west flows between subnets/VNets, north-south egress paths lacking inspection, unexpected internet exposure, flows bypassing the firewall, and unencrypted plaintext protocols in use. Evaluate whether traffic inspection is symmetric and complete.",
  dependency_chains:
    "Map and analyze resource dependency chains across the network topology. Identify: single points of failure in connectivity paths, circular routing dependencies, implicit dependencies between subnets and shared services (DNS, NTP, AD), and missing redundancy in critical paths such as VPN/ExpressRoute, NAT Gateways, and load balancers.",
  interconnect:
    "Evaluate all interconnect behaviors: VNet peering configurations (allow_gateway_transit, use_remote_gateways, allow_forwarded_traffic), VPN Gateway connections (BGP, active/active, route advertisement), ExpressRoute circuit peerings (private vs. Microsoft peering, global reach), vWAN hub routing, and cross-subscription/cross-tenant connectivity risks. Identify asymmetric routing, route leaking, and unauthorized transit paths.",
  routing_decisions:
    "Analyze all routing decisions: UDRs overriding system routes, BGP route advertisement scope, next-hop configurations (NVA vs. Azure Firewall vs. Internet), default route (0.0.0.0/0) propagation, and route priority conflicts. Identify routes that could bypass inspection, create traffic black holes, or expose internal prefixes to unauthorized next-hops.",
  resilience:
    "Evaluate network resilience assumptions: zone redundancy for Gateways, Firewalls, Load Balancers, and NAT Gateways; active/active vs. active/passive VPN/ExpressRoute; health probe coverage on load balancers; failover behavior during zone or region outage; dependency on single-instance components; and DDoS protection coverage. Identify SLA-breaking single points of failure.",
};

// ── Shared JSON schema instruction ────────────────────────────────────────────

const FINDING_SCHEMA = `Return ONLY a JSON object in this exact format:
{
  "findings": [
    {
      "title": "string — concise, specific finding title",
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL",
      "category": "string — e.g. Network Segmentation, Traffic Inspection, Routing, Resilience, Compliance, Encryption, Access Control",
      "description": "string — detailed explanation of the issue, what was observed, and its specific risk",
      "recommendation": "string — numbered remediation steps specific to Azure",
      "msLearnLinks": ["array of 2-4 real Microsoft Learn URLs directly relevant to this finding"],
      "frameworkMapping": "string — e.g. NIST SC-7, CIS 6.4 (or null if not applicable)"
    }
  ]
}`;

const MS_LEARN_INSTRUCTION = `For each finding, include 2-4 real Microsoft Learn documentation URLs in msLearnLinks.
Use only these verified URL patterns:
- https://learn.microsoft.com/azure/firewall/...
- https://learn.microsoft.com/azure/virtual-network/...
- https://learn.microsoft.com/azure/network-watcher/...
- https://learn.microsoft.com/azure/load-balancer/...
- https://learn.microsoft.com/azure/vpn-gateway/...
- https://learn.microsoft.com/azure/expressroute/...
- https://learn.microsoft.com/azure/ddos-protection/...
- https://learn.microsoft.com/azure/private-link/...
- https://learn.microsoft.com/azure/bastion/...
- https://learn.microsoft.com/security/benchmark/azure/...
- https://learn.microsoft.com/azure/well-architected/...
Use the exact page slug — only include URLs you are confident exist.`;

// ── Topology summary helper ───────────────────────────────────────────────────

function summarizeTopology(topologyJson: string): string {
  try {
    const topo = JSON.parse(topologyJson);
    const subs = topo.subscriptions ?? [];
    const lines: string[] = ["=== DISCOVERED AZURE TOPOLOGY ==="];
    for (const sub of subs) {
      lines.push(`\nSubscription: ${sub.subscription_name ?? sub.subscription_id}`);
      if (sub.discovery_blocked) {
        lines.push(`  [BLOCKED: ${sub.block_reason ?? "insufficient permissions"}]`);
        continue;
      }
      const vnets = sub.vnets ?? [];
      lines.push(`  VNets (${vnets.length}):`);
      for (const v of vnets) {
        lines.push(`    - ${v.name} [${(v.address_space ?? []).join(", ")}] loc=${v.location} rg=${v.resource_group}`);
        lines.push(`      DNS: ${(v.dns_servers ?? []).join(", ") || "Azure Default"}`);
        lines.push(`      DDoS: ${v.ddos_protection_enabled ? "enabled" : "NOT ENABLED"}`);
        lines.push(`      Encryption: ${v.encryption_enabled ? "enabled" : "disabled"}`);
        const subnets = v.subnets ?? [];
        lines.push(`      Subnets (${subnets.length}):`);
        for (const s of subnets) {
          const nsgStatus = s.nsg_name ? `NSG:${s.nsg_name}` : "NO-NSG";
          const rtStatus = s.route_table_name ? `RT:${s.route_table_name}` : "NO-UDR";
          const natStatus = s.nat_gateway_id ? "NAT-GW" : "";
          const delegated = s.delegation ? `delegated:${s.delegation}` : "";
          lines.push(`        * ${s.name} ${s.address_prefix} [${[nsgStatus, rtStatus, natStatus, delegated].filter(Boolean).join(" | ")}]`);
          if (s.service_endpoints?.length) {
            lines.push(`          ServiceEndpoints: ${s.service_endpoints.join(", ")}`);
          }
        }
        const peerings = v.peerings ?? [];
        if (peerings.length) {
          lines.push(`      Peerings:`);
          for (const p of peerings) {
            lines.push(`        - ${p.name} → ${p.remote_vnet_name ?? p.remote_vnet_id} state=${p.peering_state} gwTransit=${p.allow_gateway_transit} useRemoteGW=${p.use_remote_gateways}`);
          }
        }
      }
      // NSGs
      const nsgs = sub.nsgs ?? [];
      if (nsgs.length) {
        lines.push(`  NSGs (${nsgs.length}):`);
        for (const nsg of nsgs) {
          lines.push(`    - ${nsg.name} rg=${nsg.resource_group} subnets=${nsg.associated_subnet_ids?.length ?? 0} nics=${nsg.associated_nic_ids?.length ?? 0}`);
          const rules = nsg.security_rules ?? [];
          lines.push(`      Custom rules: ${rules.length}`);
          for (const r of rules.slice(0, 20)) {
            const src = r.source_address_prefix ?? (r.source_address_prefixes ?? []).join(",");
            const dst = r.destination_address_prefix ?? (r.destination_address_prefixes ?? []).join(",");
            const port = r.destination_port_range ?? (r.destination_port_ranges ?? []).join(",");
            lines.push(`        [${r.priority}] ${r.direction} ${r.access} proto=${r.protocol} src=${src} dst=${dst} port=${port}`);
          }
          if (rules.length > 20) lines.push(`        ... ${rules.length - 20} more rules`);
        }
      }
      // Route Tables
      const rts = sub.route_tables ?? [];
      if (rts.length) {
        lines.push(`  Route Tables (${rts.length}):`);
        for (const rt of rts) {
          lines.push(`    - ${rt.name} subnets=${rt.associated_subnet_ids?.length ?? 0} bgpPropagation=${!rt.disable_bgp_route_propagation}`);
          for (const r of rt.routes ?? []) {
            lines.push(`      ${r.name}: ${r.address_prefix} → ${r.next_hop_type}${r.next_hop_ip ? ` (${r.next_hop_ip})` : ""}`);
          }
        }
      }
      // VNet Gateways
      const gws = sub.virtual_network_gateways ?? [];
      if (gws.length) {
        lines.push(`  VNet Gateways (${gws.length}):`);
        for (const gw of gws) {
          lines.push(`    - ${gw.name} type=${gw.gateway_type} sku=${gw.sku_name} activeActive=${gw.active_active} bgp=${gw.enable_bgp} asn=${gw.bgp_asn ?? "N/A"}`);
          for (const c of gw.connections ?? []) {
            lines.push(`      Conn: ${c.name} type=${c.connection_type} status=${c.connection_status} bgp=${c.enable_bgp}`);
          }
        }
      }
      // Load Balancers
      const lbs = sub.load_balancers ?? [];
      if (lbs.length) {
        lines.push(`  Load Balancers (${lbs.length}):`);
        for (const lb of lbs) {
          lines.push(`    - ${lb.name} sku=${lb.sku_name} type=${lb.lb_type} rules=${lb.lb_rules?.length ?? 0} probes=${lb.probes?.length ?? 0} zones=${(lb.zones ?? []).join(",") || "none"}`);
        }
      }
      // Public IPs
      const pips = sub.public_ips ?? [];
      const unassociated = pips.filter((p: Record<string, unknown>) => !p.associated_resource_id);
      lines.push(`  Public IPs (${pips.length}): ${unassociated.length} unassociated`);
      for (const pip of pips) {
        lines.push(`    - ${pip.name} ${pip.ip_address ?? "dynamic"} sku=${pip.sku_name} alloc=${pip.allocation_method} assocType=${pip.associated_resource_type ?? "UNASSOCIATED"}`);
      }
      // Private Endpoints
      const pes = sub.private_endpoints ?? [];
      lines.push(`  Private Endpoints (${pes.length}):`);
      for (const pe of pes) {
        const svcs = (pe.service_connections ?? []).map((c: Record<string, unknown>) => `${c.private_link_service_id?.toString().split("/").slice(-1)[0]}[${c.connection_state}]`).join(", ");
        lines.push(`    - ${pe.name} subnet=${pe.subnet_id?.split("/").slice(-1)[0]} services=${svcs || "?"}`);
      }
      // NAT Gateways
      const nats = sub.nat_gateways ?? [];
      if (nats.length) {
        lines.push(`  NAT Gateways (${nats.length}):`);
        for (const ng of nats) {
          lines.push(`    - ${ng.name} pips=${ng.public_ip_ids?.length ?? 0} subnets=${ng.associated_subnet_ids?.length ?? 0} timeout=${ng.idle_timeout_minutes}min`);
        }
      }
      // Bastions
      const bastions = sub.bastion_hosts ?? [];
      if (bastions.length) {
        lines.push(`  Bastion Hosts (${bastions.length}):`);
        for (const b of bastions) {
          lines.push(`    - ${b.name} sku=${b.sku_name} tunneling=${b.tunneling_enabled} shareableLink=${b.shareable_link_enabled}`);
        }
      }
      // Firewalls
      const fws = sub.firewalls ?? [];
      if (fws.length) {
        lines.push(`  Azure Firewalls (${fws.length}):`);
        for (const fw of fws) {
          lines.push(`    - ${fw.name} sku=${fw.sku_tier} threatIntel=${fw.threat_intel_mode} pips=${fw.public_ip_ids?.length ?? 0} zones=${(fw.zones ?? []).join(",") || "none"}`);
        }
      } else {
        lines.push(`  Azure Firewalls: NONE DEPLOYED`);
      }
      // App Gateways
      const agws = sub.application_gateways ?? [];
      if (agws.length) {
        lines.push(`  Application Gateways (${agws.length}):`);
        for (const agw of agws) {
          lines.push(`    - ${agw.name} sku=${agw.sku_name} waf=${agw.waf_enabled} wafMode=${agw.waf_mode ?? "N/A"} ruleSet=${agw.waf_rule_set_type ?? "N/A"}/${agw.waf_rule_set_version ?? "N/A"} zones=${(agw.zones ?? []).join(",") || "none"}`);
        }
      }
      // Private DNS
      const dns = sub.private_dns_zones ?? [];
      if (dns.length) {
        lines.push(`  Private DNS Zones (${dns.length}):`);
        for (const z of dns) {
          lines.push(`    - ${z.name} records=${z.record_count} linkedVnets=${z.linked_vnet_ids?.length ?? 0} autoReg=${z.auto_registration_enabled}`);
        }
      }
      // ExpressRoute
      const ers = sub.express_route_circuits ?? [];
      if (ers.length) {
        lines.push(`  ExpressRoute Circuits (${ers.length}):`);
        for (const er of ers) {
          lines.push(`    - ${er.name} provider=${er.service_provider ?? "?"} bw=${er.bandwidth_mbps ?? "?"}Mbps sku=${er.sku_tier} peeringTypes=${(er.peering_types ?? []).join(",") || "?"} globalReach=${er.global_reach_enabled}`);
        }
      }
    }
    return lines.join("\n");
  } catch {
    return "[topology JSON could not be parsed]";
  }
}

// ── Core analysis function ────────────────────────────────────────────────────

/**
 * Comprehensive engagement analysis using topology, documents, and existing findings.
 * All three data sources are passed to the AI for a complete picture.
 */
export async function analyzeEngagement(
  options: {
    topologyJson?: string | null;
    documents?: { fileName: string; text: string }[];
    existingFindings?: { title: string; severity: string; category: string; description: string }[];
    focus: AnalysisFocus;
    extraInstruction?: string;
  },
): Promise<RawFinding[]> {
  const { topologyJson, documents = [], existingFindings = [], focus, extraInstruction } = options;
  const client = getClient();
  const focusInstruction = FOCUS_PROMPTS[focus];

  const systemPrompt = `You are a senior Azure cloud network security architect performing a Cloud Network Assessment (CNA) for a CBTS customer engagement.
You have access to three data sources: live-discovered topology, uploaded documents, and existing findings from automated rules.

ANALYSIS FOCUS: ${focusInstruction}

CRITICAL REQUIREMENTS:
- Every finding must reference specific, observed evidence from the data provided.
- Do not repeat findings that already exist in the existing findings list.
- Each recommendation must contain numbered steps with specific Azure portal paths, CLI commands, or Bicep/ARM patterns.
- Every finding must include 2-4 real Microsoft Learn documentation links.
- Severity definitions: CRITICAL=active exploit risk/data exposure, HIGH=likely path to compromise, MEDIUM=weakens defense-in-depth, LOW=best practice deviation, INFORMATIONAL=configuration note.

${MS_LEARN_INSTRUCTION}

${FINDING_SCHEMA}`;

  const parts: string[] = [];

  if (topologyJson) {
    parts.push(summarizeTopology(topologyJson));
  }

  if (existingFindings.length > 0) {
    parts.push(
      "\n=== EXISTING FINDINGS (do NOT duplicate these) ===\n" +
      existingFindings.map((f) => `- [${f.severity}] ${f.title}: ${f.category}`).join("\n"),
    );
  }

  if (documents.length > 0) {
    parts.push(
      "\n=== UPLOADED DOCUMENTS ===\n" +
      documents
        .map((d, i) => `--- Document ${i + 1}: ${d.fileName} ---\n${d.text.slice(0, 8000)}`)
        .join("\n\n"),
    );
  }

  if (parts.length === 0) {
    return [];
  }

  const userPrompt = `Perform a ${FOCUS_LABELS[focus]} analysis on the following network assessment data. Identify security findings not already covered by existing findings:${extraInstruction ? `\n\n${extraInstruction}` : ""}\n\n${parts.join("\n\n")}`;

  const deployment = process.env.AZURE_OPENAI_DEPLOYMENT ?? "gpt-4o";
  const response = await client.chat.completions.create({
    model: deployment,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
    response_format: { type: "json_object" },
    temperature: 0.15,
    max_tokens: 8000,
  });

  const raw = response.choices[0]?.message?.content ?? "{}";
  const parsed = JSON.parse(raw) as { findings?: RawFinding[] };
  return parsed.findings ?? [];
}

// ── Legacy wrapper — kept for backward compatibility ──────────────────────────

export async function analyzeDocuments(
  documents: { fileName: string; text: string }[],
  focus: AnalysisFocus = "general",
): Promise<RawFinding[]> {
  return analyzeEngagement({ documents, focus });
}

// ── Deliverable generation ────────────────────────────────────────────────────

export type DeliverableType =
  | "EXECUTIVE_SUMMARY"
  | "TECHNICAL_FINDINGS"
  | "REMEDIATION_PLAN"
  | "SPECIALIZATION_REPORT"
  | "COMPREHENSIVE_ASSESSMENT";

export interface DeliverableContext {
  type: DeliverableType;
  title: string;
  clientOrg: string;
  engagementName: string;
  findings: Array<{
    id: string;
    title: string;
    severity: string;
    category: string;
    description: string;
    recommendation: string | null;
    aiGenerated: boolean;
  }>;
  topologyJson?: string | null;
  documents?: { fileName: string; text: string }[];
  customerLogoUrl?: string | null;
}

const DELIVERABLE_PROMPTS: Record<DeliverableType, string> = {
  EXECUTIVE_SUMMARY: `You are producing a board-ready Executive Summary for a Cloud Network Assessment.
REQUIREMENTS:
- Open with a 2-3 sentence plain-English risk posture statement (no jargon).
- Cover ALL findings by name and explain their business risk — do NOT limit to top 5 or any subset. Every finding must appear.
- Group findings by severity (CRITICAL first) with a business-impact explanation for each.
- Include a severity breakdown table (CRITICAL/HIGH/MEDIUM/LOW/INFO counts and percentages).
- Write a "Business Impact" section mapping network risks to business outcomes (downtime, data breach, compliance penalty).
- Write "Recommended Next Steps" as a prioritized action list with 30/60/90-day horizon.
- Include 2-3 Microsoft Learn links for key best practices.
- Tone: executive, outcome-focused, no CLI commands.
- Format: professional Markdown, ready to convert to PDF.`,

  TECHNICAL_FINDINGS: `You are producing a Technical Findings Report for network engineers.
REQUIREMENTS:
- Group all findings by severity (CRITICAL first), then by category.
- For each finding: title, severity badge, category, detailed technical description, root cause, business impact, and a numbered remediation guide with Azure CLI/portal steps.
- Include at least 3 Microsoft Learn links per finding.
- Include framework mapping (NIST SP 800-53, CIS Azure) where applicable.
- Add a "Discovery Scope" section summarizing what was scanned (VNets, NSGs, etc.).
- Add a "Risk Matrix" table: rows=categories, columns=severities.
- Format: professional Markdown with clear headings and tables.`,

  REMEDIATION_PLAN: `You are producing a detailed Remediation Plan for an IT/platform team.
REQUIREMENTS:
- Open with an executive risk summary (2-3 sentences).
- Prioritize all findings by combined risk score (severity + exploitability + effort).
- For each finding, produce a numbered task entry with:
  1. Finding name and severity
  2. Why it matters (1-2 sentences)
  3. Exact remediation steps (numbered, with Azure CLI commands or portal navigation paths)
  4. Validation steps (how to confirm the fix worked)
  5. Rollback procedure if the change causes issues
  6. Estimated effort (hours)
  7. 2-3 Microsoft Learn links
- Organize into a 30/60/90-day implementation roadmap section.
- Include a dependency table (which tasks must precede others).
- Format: professional Markdown, structured for a project team.`,

  SPECIALIZATION_REPORT: `You are producing a deep-dive Specialization Report for a security architect.
REQUIREMENTS:
- Open with the specific domain focus and scope.
- Perform a framework gap analysis (NIST SP 800-53, CIS Azure Foundations Benchmark, Azure WAF Security pillar) against discovered findings.
- Map every finding to specific framework control identifiers.
- Include a "Maturity Assessment" section scoring the network security posture from 1-5 across key domains.
- Add an "Architecture Recommendations" section with design patterns and Azure reference architecture links.
- Include 4-5 Microsoft Learn links per major section.
- Add a compliance gap register table: control ID, requirement, current state, gap, remediation.
- Format: professional Markdown with executive and technical layers.`,

  COMPREHENSIVE_ASSESSMENT: `You are acting as a Principal Network Architect, Security Analyst, and Enterprise Systems Auditor combined.
Your objective is to produce the most exhaustive, analytical, and insight-driven network assessment possible, leaving no dimension unexplored.

GOAL: Produce a fully comprehensive network assessment that:
- Captures all available data
- Performs deep analysis across every relevant domain
- Surfaces insights, risks, correlations, and improvement opportunities
- Presents results in a single interactive static web page (HTML/CSS/JS — no backend, no external CDN dependencies)

Nothing should be assumed as "out of scope" unless explicitly stated.

SCOPE — You MUST cover ALL of the following dimensions:

1. Network Architecture
   - Physical & logical topology; segmentation, routing, switching, overlays
   - Dependency mapping and traffic flows

2. Performance & Reliability
   - Latency, throughput, packet loss, jitter
   - Bottlenecks, saturation points, SPOFs; historical trends and anomaly detection

3. Security & Risk
   - Attack surface analysis; trust boundaries, exposure points
   - Control gaps, misconfigurations, threat modeling
   - Risk scoring and prioritization matrix

4. Operational Maturity
   - Monitoring, alerting, observability coverage
   - Incident response readiness; change management and operational debt

5. Compliance & Governance
   - Alignment to NIST, ISO, CIS (conceptually)
   - Policy adherence vs. actual state; audit readiness indicators

6. Scalability & Future Readiness
   - Growth constraints; cloud/hybrid implications
   - Automation and programmability gaps

7. Cost & Efficiency
   - Resource utilization; redundancy vs. waste
   - Cost-risk-performance tradeoffs

DATA UTILIZATION RULES:
- Use all provided data; do not summarize away detail.
- If data is incomplete, explicitly identify gaps, infer cautiously, and label assumptions.
- Cross-correlate data between domains (e.g., performance issues tied to security controls or architecture decisions).

REQUIRED OUTPUTS (Non-Negotiable):
1. Structured Tables & Matrices
   - Risk matrix (impact × likelihood)
   - Control coverage matrix
   - Dependency and failure-impact matrix
   - Findings-to-recommendations traceability table

2. Narrative Analysis
   - What is happening; why it matters
   - What breaks under stress; second- and third-order effects

3. Visual Representations
   - Logical topology diagrams (text-described using ASCII/Unicode)
   - Flow and dependency representations (Unicode box-drawing or ASCII)

QUALITY & COMPLETENESS: Before finalizing, self-audit:
- List all covered domains
- Explicitly state what was analyzed
- Explicitly state what could NOT be analyzed and why
- Confirm no major network assessment dimension was omitted

TONE & STYLE: Analytical, precise, and executive-ready. No fluff, no generic advice. Insight-dense and thought-provoking.

CRITICAL OUTPUT REQUIREMENT:
Output ONLY a complete, self-contained HTML document.
- Start with <!DOCTYPE html>
- All CSS must be inline in a <style> block — dark professional theme (dark navy/slate background, teal accents)
- All JavaScript must be inline in <script> blocks
- Implement: section navigation (sticky top nav), expand/collapse sections, interactive sortable/filterable tables, clear visual hierarchy
- No external CDN links — no Bootstrap, no Tailwind CDN, no external fonts (use system fonts)
- The page must work when opened directly in a browser from disk
- Include a "Print to PDF" button that triggers window.print() with appropriate print CSS (@media print)
- NO markdown — pure HTML/CSS/JS output only`,
};

/**
 * Generate professional AI-powered deliverable content.
 * Uses all available engagement data for maximum context.
 */
export async function generateDeliverableContent(
  ctx: DeliverableContext,
): Promise<string> {
  const client = getClient();

  const typePrompt = DELIVERABLE_PROMPTS[ctx.type];
  const date = new Date().toISOString().split("T")[0];

  const systemPrompt = `You are a senior CBTS cloud network security consultant generating a professional client deliverable.
${typePrompt}

OUTPUT: Return only the Markdown document content. No JSON wrapper. Start directly with the document heading.
Include a professional document header with: Client, Engagement, Date, Report Type, Prepared By: CBTS Cloud Security Practice.`;

  const parts: string[] = [
    `# ${ctx.title}`,
    `**Client:** ${ctx.clientOrg}  `,
    `**Engagement:** ${ctx.engagementName}  `,
    `**Date:** ${date}  `,
    "",
    `=== FINDINGS DATA (${ctx.findings.length} total) ===`,
  ];

  // Add findings grouped by severity
  const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];
  for (const sev of SEV_ORDER) {
    const group = ctx.findings.filter((f) => f.severity === sev);
    if (!group.length) continue;
    parts.push(`\n[${sev} - ${group.length} findings]`);
    for (const f of group) {
      parts.push(`Finding: ${f.title}`);
      parts.push(`  Category: ${f.category}`);
      parts.push(`  Description: ${f.description}`);
      parts.push(`  Recommendation: ${f.recommendation ?? ""}`);
      parts.push(`  Source: ${f.aiGenerated ? "AI Analysis" : "Live Discovery"}`);
    }
  }

  if (ctx.topologyJson) {
    parts.push("\n" + summarizeTopology(ctx.topologyJson));
  }

  if (ctx.documents && ctx.documents.length > 0) {
    parts.push("\n=== UPLOADED DOCUMENTS ===");
    for (const doc of ctx.documents) {
      parts.push(`--- ${doc.fileName} ---\n${doc.text.slice(0, 4000)}`);
    }
  }

  const userPrompt = `Generate the ${ctx.type.replace(/_/g, " ")} deliverable using this engagement data:\n\n${parts.join("\n")}`;

  const deployment = process.env.AZURE_OPENAI_DEPLOYMENT ?? "gpt-4o";
  // Comprehensive assessment needs maximum token budget for the full HTML page
  const maxTokens = ctx.type === "COMPREHENSIVE_ASSESSMENT" ? 32000 : 16000;

  const response = await client.chat.completions.create({
    model: deployment,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
    temperature: 0.2,
    max_tokens: maxTokens,
  });

  return response.choices[0]?.message?.content ?? "# Error generating content\n\nPlease try again.";
}
