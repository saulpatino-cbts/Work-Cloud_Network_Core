import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";

interface PageProps {
  params: Promise<{ id: string }>;
}

const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"] as const;
type Sev = typeof SEV_ORDER[number];

const SEV_STYLE: Record<Sev, { bar: string; text: string; bg: string; badge: string }> = {
  CRITICAL:      { bar: "bg-red-500",    text: "text-red-600 dark:text-red-400",       bg: "border-red-200 bg-red-50/60 dark:border-red-800/40 dark:bg-red-900/10",          badge: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  HIGH:          { bar: "bg-orange-500", text: "text-orange-600 dark:text-orange-400", bg: "border-orange-200 bg-orange-50/60 dark:border-orange-800/40 dark:bg-orange-900/10", badge: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  MEDIUM:        { bar: "bg-amber-400",  text: "text-amber-600 dark:text-amber-400",   bg: "border-amber-200 bg-amber-50/60 dark:border-amber-800/40 dark:bg-amber-900/10",   badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  LOW:           { bar: "bg-blue-400",   text: "text-blue-600 dark:text-blue-400",     bg: "border-blue-200 bg-blue-50/60 dark:border-blue-800/40 dark:bg-blue-900/10",       badge: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
  INFORMATIONAL: { bar: "bg-navy-300",   text: "text-navy-500 dark:text-navy-300",     bg: "border-navy-100 bg-navy-50/60 dark:border-navy-700/40 dark:bg-navy-800/20",       badge: "bg-navy-100 text-navy-500 dark:bg-navy-700/40 dark:text-navy-300" },
};

export default async function PresentationPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    include: {
      members: true,
      findings: { orderBy: [{ severity: "asc" }, { category: "asc" }] },
      deliverables: { orderBy: { createdAt: "desc" } },
      documents: { select: { id: true, fileName: true, docType: true, createdAt: true } },
    },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  let topology: {
    subscriptions: {
      subscription_name: string | null;
      subscription_id: string;
      vnets: {
        name: string;
        address_space: string[];
        location: string;
        subnets: { name: string; address_prefix: string; nsg_name: string | null; nsg_id: string | null }[];
      }[];
      firewalls: { name: string; sku_tier: string; threat_intel_mode: string }[];
      load_balancers: { name: string; sku_name: string; lb_type: string }[];
      nsgs: { name: string; security_rules: unknown[] }[];
    }[];
  } | null = null;
  let jobDate: Date | null = null;

  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { topologyJson: true, completedAt: true },
    });
    if (job?.topologyJson) {
      try { topology = JSON.parse(job.topologyJson); } catch { /* ignore */ }
    }
    jobDate = job?.completedAt ?? null;
  } catch { /* migration pending */ }

  const { findings } = engagement;
  const bySev: Record<Sev, typeof findings> = {} as Record<Sev, typeof findings>;
  for (const sev of SEV_ORDER) {
    bySev[sev] = findings.filter((f) => f.severity === sev);
  }

  const categories = [...new Set(findings.map((f) => f.category))].sort();
  const date = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });

  const totalVnets = topology?.subscriptions.reduce((n, s) => n + (s.vnets?.length ?? 0), 0) ?? 0;
  const totalSubnets = topology?.subscriptions.reduce(
    (n, s) => n + s.vnets.reduce((m, v) => m + (v.subnets?.length ?? 0), 0), 0
  ) ?? 0;

  return (
    <div className="mx-auto max-w-4xl space-y-4 print:max-w-full print:space-y-6">
      {/* Print button */}
      <div className="flex items-center justify-between print:hidden">
        <p className="label-caps text-navy-300 dark:text-navy-500">Full Report View</p>
        <button
          type="button"
          onClick={() => window.print()}
          className="btn-teal text-sm"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
          </svg>
          Print / Save PDF
        </button>
      </div>

      {/* ── Cover ── */}
      <div className="glass p-8 print:break-inside-avoid">
        <p className="label-caps text-teal-600 dark:text-teal-400">Cloud Network Assessment</p>
        <h1 className="mt-3 text-4xl font-black tracking-tight text-navy-800 dark:text-navy-50">
          {engagement.clientOrg}
        </h1>
        <p className="mt-2 text-xl font-medium text-navy-500 dark:text-navy-300">
          {engagement.name}
        </p>
        <p className="mt-2 text-sm text-navy-400 dark:text-navy-400">{date}</p>
        {jobDate && (
          <p className="mt-0.5 text-xs text-navy-400 dark:text-navy-500">
            Discovery completed: {new Date(jobDate).toLocaleDateString()}
          </p>
        )}

        {findings.length > 0 && (
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {SEV_ORDER.map((sev) => bySev[sev].length > 0 ? (
              <div key={sev} className={`rounded-xl border p-3 text-center ${SEV_STYLE[sev].bg}`}>
                <p className={`text-2xl font-black ${SEV_STYLE[sev].text}`}>
                  {bySev[sev].length}
                </p>
                <p className={`mt-0.5 text-xs font-semibold ${SEV_STYLE[sev].text}`}>
                  {sev[0] + sev.slice(1).toLowerCase()}
                </p>
              </div>
            ) : null)}
          </div>
        )}

        {/* Severity bar */}
        {findings.length > 0 && (
          <div className="mt-4">
            <div className="flex h-2.5 w-full overflow-hidden rounded-full">
              {SEV_ORDER.map((sev) => {
                const pct = (bySev[sev].length / findings.length) * 100;
                return pct > 0 ? (
                  <div
                    key={sev}
                    className={`bar-fill ${SEV_STYLE[sev].bar}`}
                    style={{ '--bar-pct': `${pct}%` } as React.CSSProperties}
                    title={`${sev}: ${bySev[sev].length}`}
                  />
                ) : null;
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Table of Contents ── */}
      <div className="glass p-6 print:break-inside-avoid">
        <h2 className="mb-4 text-base font-bold text-navy-700 dark:text-navy-100">
          Table of Contents
        </h2>
        <nav className="grid gap-2 sm:grid-cols-2">
          {[
            { href: "#executive-summary", label: "1. Executive Summary" },
            { href: "#risk-matrix", label: "2. Risk Matrix" },
            { href: "#finding-details", label: "3. Finding Details" },
            topology && { href: "#network-inventory", label: "4. Network Inventory" },
            engagement.deliverables.length > 0 && { href: "#deliverables", label: "5. Deliverables" },
            engagement.documents.length > 0 && { href: "#documents", label: "6. Reference Documents" },
          ].filter(Boolean).map((item) => item && (
            <a
              key={item.href}
              href={item.href}
              className="rounded-lg border border-navy-100/60 px-3 py-2 text-sm text-teal-600 transition-colors hover:border-teal-400/40 hover:bg-teal-50/40 dark:border-navy-700/40 dark:text-teal-400 dark:hover:border-teal-600/40 dark:hover:bg-teal-900/20"
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>

      {/* ── Executive Summary ── */}
      <div id="executive-summary" className="glass p-6 print:break-inside-avoid">
        <h2 className="mb-4 border-b border-navy-100/40 pb-2 text-base font-bold text-navy-700 dark:border-navy-700/40 dark:text-navy-100">
          1. Executive Summary
        </h2>
        <p className="text-sm leading-relaxed text-navy-600 dark:text-navy-200">
          This Cloud Network Assessment identified{" "}
          <strong className="text-navy-800 dark:text-navy-50">{findings.length} security finding{findings.length !== 1 ? "s" : ""}</strong>{" "}
          across the {engagement.clientOrg} Azure environment
          {topology ? ` spanning ${topology.subscriptions.length} subscription${topology.subscriptions.length !== 1 ? "s" : ""}, ${totalVnets} VNet${totalVnets !== 1 ? "s" : ""}, and ${totalSubnets} subnets` : ""}.
        </p>
        {findings.length > 0 && (
          <div className="mt-5 grid gap-3 sm:grid-cols-5">
            {SEV_ORDER.map((sev) => (
              <div key={sev} className={`rounded-xl border p-4 text-center ${SEV_STYLE[sev].bg}`}>
                <p className={`text-3xl font-black ${SEV_STYLE[sev].text}`}>
                  {bySev[sev].length}
                </p>
                <p className={`mt-0.5 text-xs font-bold uppercase tracking-wide ${SEV_STYLE[sev].text}`}>
                  {sev[0] + sev.slice(1).toLowerCase()}
                </p>
              </div>
            ))}
          </div>
        )}
        {findings.length === 0 && (
          <p className="mt-4 text-sm text-navy-400 dark:text-navy-500">
            No findings recorded yet. Run discovery and AI analysis to populate the report.
          </p>
        )}
      </div>

      {/* ── Risk Matrix ── */}
      {findings.length > 0 && categories.length > 0 && (
        <div id="risk-matrix" className="glass overflow-hidden p-6 print:break-inside-avoid">
          <h2 className="mb-4 border-b border-navy-100/40 pb-2 text-base font-bold text-navy-700 dark:border-navy-700/40 dark:text-navy-100">
            2. Risk Matrix
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-navy-100/40 dark:border-navy-700/40">
                  <th className="pb-2.5 text-left text-xs font-semibold text-navy-400 dark:text-navy-500">Category</th>
                  {SEV_ORDER.map((s) => (
                    <th key={s} className={`pb-2.5 text-center text-xs font-semibold ${SEV_STYLE[s].text}`}>
                      {s[0] + s.slice(1).toLowerCase()}
                    </th>
                  ))}
                  <th className="pb-2.5 text-center text-xs font-semibold text-navy-400 dark:text-navy-500">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
                {categories.map((cat) => {
                  const cells = SEV_ORDER.map((sev) =>
                    findings.filter((f) => f.category === cat && f.severity === sev).length,
                  );
                  const total = cells.reduce((a, b) => a + b, 0);
                  return (
                    <tr key={cat}>
                      <td className="py-2 pr-4 text-xs font-medium text-navy-700 dark:text-navy-200">{cat}</td>
                      {cells.map((count, i) => (
                        <td key={i} className="py-2 text-center">
                          {count > 0 ? (
                            <span className={`inline-flex h-6 w-6 items-center justify-center rounded text-xs font-bold text-white ${SEV_STYLE[SEV_ORDER[i]].bar}`}>
                              {count}
                            </span>
                          ) : (
                            <span className="text-navy-200 dark:text-navy-700">—</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2 text-center text-xs font-bold text-navy-700 dark:text-navy-200">{total}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Finding Details ── */}
      {findings.length > 0 && (
        <div id="finding-details" className="glass p-6 print:break-inside-avoid">
          <h2 className="mb-4 border-b border-navy-100/40 pb-2 text-base font-bold text-navy-700 dark:border-navy-700/40 dark:text-navy-100">
            3. Finding Details
          </h2>
          <div className="space-y-5">
            {SEV_ORDER.map((sev) =>
              bySev[sev].length > 0 ? (
                <div key={sev}>
                  <p className={`mb-3 text-xs font-bold uppercase tracking-widest ${SEV_STYLE[sev].text}`}>
                    {sev[0] + sev.slice(1).toLowerCase()} ({bySev[sev].length})
                  </p>
                  <div className="space-y-3">
                    {bySev[sev].map((f) => (
                      <div
                        key={f.id}
                        className={`rounded-xl border p-4 ${SEV_STYLE[sev as Sev].bg} print:break-inside-avoid`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <p className="text-sm font-semibold text-navy-800 dark:text-navy-50">
                            {f.title}
                          </p>
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${SEV_STYLE[sev as Sev].badge}`}>
                            {f.category}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-navy-600 dark:text-navy-200">
                          {f.description}
                        </p>
                        {f.recommendation && (
                          <div className="mt-3 rounded-lg bg-white/60 px-4 py-3 text-xs text-navy-700 dark:bg-navy-900/40 dark:text-navy-200">
                            <span className="font-bold text-navy-800 dark:text-navy-100">
                              Recommendation:{" "}
                            </span>
                            {f.recommendation}
                          </div>
                        )}
                        {f.aiGenerated && (
                          <p className="mt-2 text-xs text-navy-400 dark:text-navy-500">
                            Source: AI Analysis
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null,
            )}
          </div>
        </div>
      )}

      {/* ── Network Inventory ── */}
      {topology && (
        <div id="network-inventory" className="glass p-6 print:break-inside-avoid">
          <h2 className="mb-4 border-b border-navy-100/40 pb-2 text-base font-bold text-navy-700 dark:border-navy-700/40 dark:text-navy-100">
            4. Network Inventory
          </h2>

          {/* Summary stats */}
          <div className="mb-5 grid grid-cols-3 gap-3 sm:grid-cols-6">
            {[
              { label: "Subscriptions", value: topology.subscriptions.length },
              { label: "VNets", value: totalVnets },
              { label: "Subnets", value: totalSubnets },
              { label: "Firewalls", value: topology.subscriptions.reduce((n, s) => n + (s.firewalls?.length ?? 0), 0) },
              { label: "Load Balancers", value: topology.subscriptions.reduce((n, s) => n + (s.load_balancers?.length ?? 0), 0) },
              { label: "NSGs", value: topology.subscriptions.reduce((n, s) => n + (s.nsgs?.length ?? 0), 0) },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl border border-navy-100/60 bg-white/40 p-3 text-center dark:border-navy-700/40 dark:bg-navy-800/30">
                <p className="text-2xl font-black text-navy-700 dark:text-navy-100">{stat.value}</p>
                <p className="mt-0.5 text-xs text-navy-400 dark:text-navy-400">{stat.label}</p>
              </div>
            ))}
          </div>

          {topology.subscriptions.map((sub) => (
            <div key={sub.subscription_id} className="mb-5 last:mb-0">
              <p className="label-caps mb-2 text-navy-400 dark:text-navy-500">
                {sub.subscription_name ?? sub.subscription_id}
              </p>
              {sub.vnets.map((vnet) => (
                <div key={vnet.name} className="mb-3 overflow-hidden rounded-xl border border-navy-100/60 dark:border-navy-700/40 last:mb-0">
                  <div className="flex items-center justify-between bg-navy-50/60 px-4 py-2.5 dark:bg-navy-800/40">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-navy-700 dark:text-navy-100">
                        {vnet.name}
                      </span>
                      <span className="text-xs text-navy-400 dark:text-navy-500">
                        {vnet.location}
                      </span>
                    </div>
                    <span className="font-mono text-xs text-navy-500 dark:text-navy-400">
                      {vnet.address_space?.join(", ")}
                    </span>
                  </div>
                  {vnet.subnets?.length > 0 && (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-navy-100/40 dark:border-navy-700/40">
                          <th className="px-4 py-1.5 text-left font-medium text-navy-400 dark:text-navy-500">Subnet</th>
                          <th className="px-4 py-1.5 text-left font-medium text-navy-400 dark:text-navy-500">CIDR</th>
                          <th className="px-4 py-1.5 text-center font-medium text-navy-400 dark:text-navy-500">NSG</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-navy-50/60 dark:divide-navy-800/40">
                        {vnet.subnets.map((s) => {
                          const platformSubnet = [
                            "GatewaySubnet", "AzureBastionSubnet", "AzureFirewallSubnet",
                            "AzureFirewallManagementSubnet", "RouteServerSubnet",
                          ].includes(s.name);
                          const missingNsg = !s.nsg_id && !platformSubnet;
                          return (
                            <tr key={s.name} className={missingNsg ? "bg-amber-50/40 dark:bg-amber-900/10" : ""}>
                              <td className="px-4 py-1.5 text-navy-700 dark:text-navy-200">{s.name}</td>
                              <td className="px-4 py-1.5 font-mono text-navy-500 dark:text-navy-400">{s.address_prefix}</td>
                              <td className="px-4 py-1.5 text-center">
                                {s.nsg_name ? (
                                  <span className="text-teal-600 dark:text-teal-400" title={s.nsg_name}>✓</span>
                                ) : platformSubnet ? (
                                  <span className="text-navy-300 dark:text-navy-600">—</span>
                                ) : (
                                  <span className="font-medium text-amber-600 dark:text-amber-400">None</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* ── Deliverables ── */}
      {engagement.deliverables.length > 0 && (
        <div id="deliverables" className="glass p-6 print:break-inside-avoid">
          <h2 className="mb-4 border-b border-navy-100/40 pb-2 text-base font-bold text-navy-700 dark:border-navy-700/40 dark:text-navy-100">
            5. Deliverables
          </h2>
          <ul className="divide-y divide-navy-100/40 dark:divide-navy-700/40">
            {engagement.deliverables.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">{d.title}</p>
                  <p className="text-xs text-navy-400 dark:text-navy-400">
                    {d.type.replace(/_/g, " ")} · {new Date(d.createdAt).toLocaleDateString()}
                  </p>
                </div>
                {d.publishedAt ? (
                  <span className="pill-teal">Published</span>
                ) : (
                  <span className="text-xs text-navy-400 dark:text-navy-500">Draft</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Documents ── */}
      {engagement.documents.length > 0 && (
        <div id="documents" className="glass p-6 print:break-inside-avoid">
          <h2 className="mb-4 border-b border-navy-100/40 pb-2 text-base font-bold text-navy-700 dark:border-navy-700/40 dark:text-navy-100">
            6. Reference Documents
          </h2>
          <ul className="divide-y divide-navy-100/40 dark:divide-navy-700/40">
            {engagement.documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between py-2.5">
                <p className="text-sm text-navy-700 dark:text-navy-200">{doc.fileName}</p>
                <span className="text-xs text-navy-400 dark:text-navy-400">
                  {doc.docType.replace(/_/g, " ")} · {new Date(doc.createdAt).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="pb-6 text-center text-xs text-navy-400 dark:text-navy-600 print:pt-4">
        Generated by CBTS CNA Platform · {date}
      </div>
    </div>
  );
}
