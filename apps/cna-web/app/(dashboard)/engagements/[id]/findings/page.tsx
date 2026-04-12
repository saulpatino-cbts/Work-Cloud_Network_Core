import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";

interface PageProps {
  params: Promise<{ id: string }>;
}

const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"] as const;
type Sev = typeof SEV_ORDER[number];

const SEV_DOT: Record<Sev, string> = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-yellow-400",
  LOW: "bg-blue-400",
  INFORMATIONAL: "bg-navy-400",
};

const SEV_BADGE: Record<Sev, string> = {
  CRITICAL: "bg-red-900/40 text-red-400",
  HIGH: "bg-orange-900/40 text-orange-400",
  MEDIUM: "bg-yellow-900/40 text-yellow-400",
  LOW: "bg-blue-900/40 text-blue-400",
  INFORMATIONAL: "bg-navy-700/50 text-navy-300",
};

const SEV_CATEGORY_BG: Record<Sev, string> = {
  CRITICAL: "bg-red-900/20 border-red-900/30",
  HIGH: "bg-orange-900/20 border-orange-900/30",
  MEDIUM: "bg-yellow-900/15 border-yellow-900/30",
  LOW: "bg-blue-900/15 border-blue-900/30",
  INFORMATIONAL: "bg-navy-800/40 border-navy-700/40",
};

const CATEGORY_ORDER = [
  "Access Control",
  "Network Security",
  "Network Segmentation",
  "Network Protection",
  "Application Security",
  "Routing & Transit",
  "Encryption",
  "Compliance",
  "Configuration",
];

// ─── MS Learn URL mapping ──────────────────────────────────────────────────────
// Matched in order — first keyword hit wins; falls back to category, then generic.
const MSLEARN_KEYWORDS: Array<[RegExp, string]> = [
  [/azure firewall/i,         "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-firewall"],
  [/ddos/i,                   "https://learn.microsoft.com/en-us/azure/ddos-protection/ddos-protection-overview"],
  [/bastion/i,                "https://learn.microsoft.com/en-us/azure/bastion/bastion-overview"],
  [/private endpoint|private link/i, "https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview"],
  [/nat gateway/i,            "https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview"],
  [/expressroute/i,           "https://learn.microsoft.com/en-us/azure/expressroute/expressroute-introduction"],
  [/vpn gateway|site.to.site/i, "https://learn.microsoft.com/en-us/azure/vpn-gateway/vpn-gateway-about-vpngateways"],
  [/peering/i,                "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-peering-overview"],
  [/application gateway|waf/i, "https://learn.microsoft.com/en-us/azure/application-gateway/overview"],
  [/load balancer/i,          "https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview"],
  [/public ip/i,              "https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-addresses"],
  [/nsg|network security group/i, "https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview"],
  [/route table|user.defined route|udr/i, "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-udr-overview"],
  [/subnet/i,                 "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-manage-subnet"],
  [/vnet|virtual network/i,   "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-overview"],
  [/flow log|network watcher/i, "https://learn.microsoft.com/en-us/azure/network-watcher/network-watcher-monitoring-overview"],
  [/encryption|tls|certificate/i, "https://learn.microsoft.com/en-us/azure/security/fundamentals/encryption-overview"],
  [/rbac|role.based|privileged/i, "https://learn.microsoft.com/en-us/azure/role-based-access-control/overview"],
  [/diagnostic|monitor|log analytics/i, "https://learn.microsoft.com/en-us/azure/azure-monitor/overview"],
  [/policy|compliance/i,      "https://learn.microsoft.com/en-us/azure/governance/policy/overview"],
];

const MSLEARN_BY_CATEGORY: Record<string, string> = {
  "Access Control":      "https://learn.microsoft.com/en-us/azure/role-based-access-control/overview",
  "Network Security":    "https://learn.microsoft.com/en-us/azure/security/fundamentals/network-overview",
  "Network Segmentation":"https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview",
  "Network Protection":  "https://learn.microsoft.com/en-us/azure/ddos-protection/ddos-protection-overview",
  "Application Security":"https://learn.microsoft.com/en-us/azure/application-gateway/overview",
  "Routing & Transit":   "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-udr-overview",
  "Encryption":          "https://learn.microsoft.com/en-us/azure/security/fundamentals/encryption-overview",
  "Compliance":          "https://learn.microsoft.com/en-us/azure/governance/policy/overview",
  "Configuration":       "https://learn.microsoft.com/en-us/azure/governance/policy/overview",
};

function getMsLearnUrl(title: string, category: string): string {
  for (const [pattern, url] of MSLEARN_KEYWORDS) {
    if (pattern.test(title)) return url;
  }
  return (
    MSLEARN_BY_CATEGORY[category] ??
    "https://learn.microsoft.com/en-us/azure/security/fundamentals/network-overview"
  );
}

export default async function FindingsPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: {
      id: true,
      name: true,
      clientOrg: true,
      members: true,
      findings: {
        orderBy: [{ severity: "asc" }, { category: "asc" }],
      },
    },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  const { findings } = engagement;

  // Build severity × category matrix
  const categories = [
    ...new Set(findings.map((f) => f.category)),
  ].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a);
    const bi = CATEGORY_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });

  const matrix: Record<string, Record<Sev, typeof findings>> = {};
  for (const cat of categories) {
    matrix[cat] = {} as Record<Sev, typeof findings>;
    for (const sev of SEV_ORDER) {
      matrix[cat][sev] = findings.filter(
        (f) => f.category === cat && f.severity === sev,
      );
    }
  }

  const bySev: Record<Sev, number> = {} as Record<Sev, number>;
  for (const sev of SEV_ORDER) {
    bySev[sev] = findings.filter((f) => f.severity === sev).length;
  }

  const liveFindings = findings.filter((f) => !f.aiGenerated);
  const aiFindings = findings.filter((f) => f.aiGenerated);

  return (
    <div className="space-y-6">
      {/* ── Summary bar ── */}
      <div className="glass p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-navy-100">
              Findings
              {findings.length > 0 && (
                <span className="ml-2 text-base font-normal text-navy-400">
                  ({findings.length} total)
                </span>
              )}
            </h2>
            <p className="mt-0.5 text-sm text-navy-400">
              {liveFindings.length} from live discovery ·{" "}
              {aiFindings.length} from AI analysis
            </p>
          </div>
          {/* Severity pills */}
          <div className="flex flex-wrap gap-2">
            {SEV_ORDER.map((sev) =>
              bySev[sev] > 0 ? (
                <div
                  key={sev}
                  className="flex items-center gap-1.5 rounded-full border border-navy-700/40 bg-navy-800/40 px-3 py-1"
                >
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${SEV_DOT[sev]}`} />
                  <span className="text-xs font-semibold text-navy-200">
                    {sev[0] + sev.slice(1).toLowerCase()}
                  </span>
                  <span className="text-xs text-navy-400">{bySev[sev]}</span>
                </div>
              ) : null,
            )}
          </div>
        </div>
      </div>

      {/* ── Risk matrix ── */}
      {findings.length > 0 && categories.length > 0 && (
        <div className="glass p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-navy-400">
            Risk Matrix — Severity × Category
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-navy-700/40">
                  <th className="w-40 pb-2 text-left text-xs font-semibold text-navy-400">
                    Category
                  </th>
                  {SEV_ORDER.map((sev) => (
                    <th key={sev} className="pb-2 text-center font-semibold text-navy-400">
                      {sev[0] + sev.slice(1).toLowerCase()}
                    </th>
                  ))}
                  <th className="pb-2 text-center font-semibold text-navy-400">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-700/30">
                {categories.map((cat) => {
                  const rowTotal = SEV_ORDER.reduce(
                    (s, sev) => s + matrix[cat][sev].length,
                    0,
                  );
                  return (
                    <tr key={cat} className="hover:bg-navy-800/30">
                      <td className="py-2 pr-4 text-xs font-medium text-navy-200">{cat}</td>
                      {SEV_ORDER.map((sev) => {
                        const count = matrix[cat][sev].length;
                        return (
                          <td key={sev} className="py-2 text-center">
                            {count > 0 ? (
                              <span className={`inline-flex h-6 w-6 items-center justify-center rounded font-bold text-white ${SEV_DOT[sev]}`}>
                                {count}
                              </span>
                            ) : (
                              <span className="text-navy-700">—</span>
                            )}
                          </td>
                        );
                      })}
                      <td className="py-2 text-center font-semibold text-navy-200">{rowTotal}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Findings list grouped by category ── */}
      {findings.length === 0 ? (
        <div className="glass rounded-xl border border-dashed border-navy-600 p-8 text-center">
          <p className="text-sm font-medium text-navy-400">No findings yet.</p>
          <p className="mt-1 text-xs text-navy-500">
            Run discovery on the Connections tab, or upload documents and run AI
            analysis above.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {liveFindings.length > 0 && (
            <FindingGroup
              title="From Live Discovery"
              findings={liveFindings}
              categories={categories}
              matrix={matrix}
              sevOrder={SEV_ORDER}
              sevBadge={SEV_BADGE}
              sevCategoryBg={SEV_CATEGORY_BG}
            />
          )}
          {aiFindings.length > 0 && (
            <FindingGroup
              title="From AI Analysis"
              findings={aiFindings}
              categories={categories}
              matrix={matrix}
              sevOrder={SEV_ORDER}
              sevBadge={SEV_BADGE}
              sevCategoryBg={SEV_CATEGORY_BG}
            />
          )}
        </div>
      )}
    </div>
  );
}

type Finding = {
  id: string;
  title: string;
  category: string;
  severity: string;
  description: string;
  recommendation: string | null;
  aiGenerated: boolean;
};

function FindingGroup({
  title,
  findings,
  categories,
  matrix,
  sevOrder,
  sevBadge,
  sevCategoryBg,
}: {
  title: string;
  findings: Finding[];
  categories: string[];
  matrix: Record<string, Record<Sev, Finding[]>>;
  sevOrder: readonly Sev[];
  sevBadge: Record<Sev, string>;
  sevCategoryBg: Record<Sev, string>;
}) {
  const relevantCategories = categories.filter((cat) =>
    findings.some((f) => f.category === cat),
  );

  return (
    <div className="glass overflow-hidden">
      <div className="border-b border-navy-700/40 px-5 py-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-navy-400">
          {title}{" "}
          <span className="ml-1 font-normal text-navy-500">({findings.length})</span>
        </h3>
      </div>
      <div className="divide-y divide-navy-700/30">
        {relevantCategories.map((cat) => {
          const catFindings = findings.filter((f) => f.category === cat);
          // Determine dominant severity for category header
          const dominantSev = sevOrder.find((sev) =>
            catFindings.some((f) => f.severity === sev),
          ) as Sev | undefined;

          return (
            <div key={cat}>
              <div className={`border-b px-5 py-2 ${dominantSev ? sevCategoryBg[dominantSev] : "bg-navy-800/30 border-navy-700/30"}`}>
                <span className="text-xs font-semibold text-navy-200">{cat}</span>
                <span className="ml-2 text-xs text-navy-400">({catFindings.length})</span>
              </div>
              <ul className="divide-y divide-navy-700/20">
                {sevOrder.map((sev) =>
                  catFindings
                    .filter((f) => f.severity === sev)
                    .map((f) => (
                      <li key={f.id} className="px-5 py-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-navy-100">{f.title}</p>
                            <p className="mt-2 text-sm text-navy-300 leading-relaxed">{f.description}</p>
                            {f.recommendation && (
                              <div className="mt-3 rounded-lg border border-teal-900/30 bg-teal-900/10 px-3 py-2">
                                <p className="text-xs text-teal-300 leading-relaxed">
                                  <span className="font-semibold text-teal-200">Recommendation: </span>
                                  {f.recommendation}
                                </p>
                                <a
                                  href={getMsLearnUrl(f.title, f.category)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-teal-400 hover:text-teal-300 hover:underline"
                                >
                                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                  </svg>
                                  MS Learn docs
                                </a>
                              </div>
                            )}
                          </div>
                          <div className="shrink-0">
                            <StatusBadge value={f.severity} variant="severity" />
                          </div>
                        </div>
                      </li>
                    )),
                )}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
