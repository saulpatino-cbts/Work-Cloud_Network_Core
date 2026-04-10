import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";

interface PageProps {
  params: Promise<{ id: string }>;
}

const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"] as const;
type Sev = typeof SEV_ORDER[number];

const SEV_BAR: Record<Sev, string> = {
  CRITICAL: "bg-red-600",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-yellow-400",
  LOW: "bg-blue-400",
  INFORMATIONAL: "bg-gray-300",
};

const SEV_TEXT: Record<Sev, string> = {
  CRITICAL: "text-red-700",
  HIGH: "text-orange-700",
  MEDIUM: "text-yellow-700",
  LOW: "text-blue-700",
  INFORMATIONAL: "text-gray-500",
};

const SEV_BG: Record<Sev, string> = {
  CRITICAL: "bg-red-50 border-red-200",
  HIGH: "bg-orange-50 border-orange-200",
  MEDIUM: "bg-yellow-50 border-yellow-200",
  LOW: "bg-blue-50 border-blue-200",
  INFORMATIONAL: "bg-gray-50 border-gray-200",
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

  let topologyJson: string | null = null;
  let jobDate: Date | null = null;
  let jobFindingsCount: number | null = null;
  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { topologyJson: true, completedAt: true, findingsCount: true },
    });
    topologyJson = job?.topologyJson ?? null;
    jobDate = job?.completedAt ?? null;
    jobFindingsCount = job?.findingsCount ?? null;
  } catch { /* migration pending */ }

  let topology: { subscriptions: { subscription_name: string | null; subscription_id: string; vnets: { name: string; address_space: string[]; subnets: { name: string; address_prefix: string; nsg_id: string | null }[] }[] }[] } | null = null;
  if (topologyJson) {
    try { topology = JSON.parse(topologyJson); } catch { /* ignore */ }
  }

  const { findings } = engagement;
  const bySev: Record<Sev, typeof findings> = {} as Record<Sev, typeof findings>;
  for (const sev of SEV_ORDER) {
    bySev[sev] = findings.filter((f) => f.severity === sev);
  }

  const categories = [...new Set(findings.map((f) => f.category))];
  const date = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });

  const allSubnets = topology?.subscriptions.flatMap((s) =>
    s.vnets.flatMap((v) =>
      v.subnets.map((sub) => ({ ...sub, vnet: v.name, sub: s.subscription_name ?? s.subscription_id })),
    ),
  ) ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-0 font-sans print:max-w-full">
      {/* ── Print button ── */}
      <div className="mb-4 flex justify-end print:hidden">
        <button
          onClick={() => window.print()}
          className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
        >
          Print / Save as PDF
        </button>
      </div>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 1 — COVER                                              */}
      {/* ══════════════════════════════════════════════════════════════ */}
      <Section id="cover" altBg>
        <div className="flex min-h-48 flex-col justify-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">
            Cloud Network Assessment
          </p>
          <h1 className="mt-3 text-4xl font-bold text-gray-900">
            {engagement.clientOrg}
          </h1>
          <p className="mt-2 text-xl text-gray-600">{engagement.name}</p>
          <p className="mt-4 text-sm text-gray-400">{date}</p>
          <div className="mt-6 flex flex-wrap gap-4 text-sm">
            <Stat label="Total Findings" value={findings.length} />
            {SEV_ORDER.filter((s) => bySev[s].length > 0).map((s) => (
              <Stat key={s} label={s[0] + s.slice(1).toLowerCase()} value={bySev[s].length} />
            ))}
          </div>
        </div>
      </Section>

      {/* ── TOC ── */}
      <Section id="toc">
        <SectionHeader>Table of Contents</SectionHeader>
        <nav className="grid gap-1.5 sm:grid-cols-2">
          {[
            { href: "#executive-summary", label: "1. Executive Summary" },
            { href: "#findings-matrix", label: "2. Risk Matrix" },
            { href: "#findings-detail", label: "3. Finding Details" },
            { href: "#network-inventory", label: "4. Network Inventory" },
            { href: "#deliverables", label: "5. Deliverables" },
            { href: "#documents", label: "6. Reference Documents" },
          ].map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-lg border border-gray-100 px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 hover:border-blue-200"
            >
              {item.label}
            </a>
          ))}
        </nav>
      </Section>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 2 — EXECUTIVE SUMMARY                                  */}
      {/* ══════════════════════════════════════════════════════════════ */}
      <Section id="executive-summary" altBg>
        <SectionHeader>1. Executive Summary</SectionHeader>
        <p className="text-sm text-gray-600 leading-relaxed">
          This Cloud Network Assessment identified{" "}
          <strong>{findings.length} security finding(s)</strong> across the{" "}
          {engagement.clientOrg} Azure environment
          {topology ? ` (${topology.subscriptions.length} subscription(s) scanned)` : ""}.
          {jobDate && (
            <> Discovery was completed on {new Date(jobDate).toLocaleDateString()}.</>
          )}
        </p>
        {findings.length > 0 && (
          <div className="mt-5 grid gap-3 sm:grid-cols-5">
            {SEV_ORDER.map((sev) => (
              <div
                key={sev}
                className={`rounded-xl border p-4 text-center ${SEV_BG[sev]}`}
              >
                <p className={`text-3xl font-bold ${SEV_TEXT[sev]}`}>
                  {bySev[sev].length}
                </p>
                <p className={`mt-1 text-xs font-semibold uppercase tracking-wide ${SEV_TEXT[sev]}`}>
                  {sev[0] + sev.slice(1).toLowerCase()}
                </p>
              </div>
            ))}
          </div>
        )}
        {/* Visual severity bar */}
        {findings.length > 0 && (
          <div className="mt-4">
            <div className="flex h-4 w-full overflow-hidden rounded-full">
              {SEV_ORDER.map((sev) => {
                const pct = (bySev[sev].length / findings.length) * 100;
                return pct > 0 ? (
                  <div
                    key={sev}
                    className={`${SEV_BAR[sev]} transition-all`}
                    style={{ width: `${pct}%` }}
                    title={`${sev}: ${bySev[sev].length}`}
                  />
                ) : null;
              })}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-3">
              {SEV_ORDER.filter((s) => bySev[s].length > 0).map((s) => (
                <span key={s} className="flex items-center gap-1.5 text-xs text-gray-500">
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${SEV_BAR[s]}`} />
                  {s[0] + s.slice(1).toLowerCase()} ({bySev[s].length})
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 3 — RISK MATRIX                                        */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {findings.length > 0 && categories.length > 0 && (
        <Section id="findings-matrix">
          <SectionHeader>2. Risk Matrix</SectionHeader>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="pb-2 text-left text-xs font-semibold text-gray-400">Category</th>
                  {SEV_ORDER.map((s) => (
                    <th key={s} className="pb-2 text-center text-xs font-semibold text-gray-400">
                      {s[0] + s.slice(1).toLowerCase()}
                    </th>
                  ))}
                  <th className="pb-2 text-center text-xs font-semibold text-gray-400">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {categories.map((cat) => {
                  const cells = SEV_ORDER.map((sev) =>
                    findings.filter((f) => f.category === cat && f.severity === sev).length,
                  );
                  const total = cells.reduce((a, b) => a + b, 0);
                  return (
                    <tr key={cat}>
                      <td className="py-2 pr-4 text-xs font-medium text-gray-700">{cat}</td>
                      {cells.map((count, i) => (
                        <td key={i} className="py-2 text-center">
                          {count > 0 ? (
                            <span className={`inline-flex h-6 w-6 items-center justify-center rounded font-bold text-white text-xs ${SEV_BAR[SEV_ORDER[i]]}`}>
                              {count}
                            </span>
                          ) : (
                            <span className="text-gray-200">—</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2 text-center text-xs font-semibold text-gray-700">{total}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 4 — FINDING DETAILS                                    */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {findings.length > 0 && (
        <Section id="findings-detail" altBg>
          <SectionHeader>3. Finding Details</SectionHeader>
          <div className="space-y-4">
            {SEV_ORDER.map((sev) =>
              bySev[sev].length > 0 ? (
                <div key={sev}>
                  <h3 className={`mb-3 text-xs font-bold uppercase tracking-widest ${SEV_TEXT[sev]}`}>
                    {sev[0] + sev.slice(1).toLowerCase()} ({bySev[sev].length})
                  </h3>
                  <div className="space-y-3">
                    {bySev[sev].map((f) => (
                      <div
                        key={f.id}
                        className={`rounded-xl border p-4 ${SEV_BG[sev as Sev]}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-semibold text-gray-900">{f.title}</p>
                          <span className="shrink-0 rounded bg-white px-1.5 py-0.5 text-xs font-medium text-gray-500 border border-gray-200">
                            {f.category}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-gray-700">{f.description}</p>
                        {f.recommendation && (
                          <div className="mt-2 rounded bg-white/60 px-3 py-2 text-xs text-gray-700">
                            <span className="font-semibold">Recommendation: </span>
                            {f.recommendation}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null,
            )}
          </div>
        </Section>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 5 — NETWORK INVENTORY                                  */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {topology && (
        <Section id="network-inventory">
          <SectionHeader>4. Network Inventory</SectionHeader>
          <div className="grid gap-3 sm:grid-cols-3 mb-5">
            <Stat label="Subscriptions" value={topology.subscriptions.length} />
            <Stat label="VNets" value={topology.subscriptions.reduce((n, s) => n + s.vnets.length, 0)} />
            <Stat label="Subnets" value={allSubnets.length} />
          </div>
          {topology.subscriptions.map((sub) => (
            <div key={sub.subscription_id} className="mb-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {sub.subscription_name ?? sub.subscription_id}
              </p>
              {sub.vnets.map((vnet) => (
                <div key={vnet.name} className="mb-3 rounded-lg border border-gray-200 overflow-hidden">
                  <div className="flex items-center justify-between bg-gray-50 px-4 py-2">
                    <span className="text-sm font-semibold text-gray-800">{vnet.name}</span>
                    <span className="font-mono text-xs text-gray-500">{vnet.address_space.join(", ")}</span>
                  </div>
                  {vnet.subnets.length > 0 && (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400">
                          <th className="px-4 py-1.5 text-left font-medium">Subnet</th>
                          <th className="px-4 py-1.5 text-left font-medium">CIDR</th>
                          <th className="px-4 py-1.5 text-center font-medium">NSG</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {vnet.subnets.map((s) => (
                          <tr key={s.name} className={!s.nsg_id && !["GatewaySubnet","AzureBastionSubnet","AzureFirewallSubnet","AzureFirewallManagementSubnet","RouteServerSubnet"].includes(s.name) ? "bg-orange-50" : ""}>
                            <td className="px-4 py-1.5 text-gray-800">{s.name}</td>
                            <td className="px-4 py-1.5 font-mono text-gray-600">{s.address_prefix}</td>
                            <td className="px-4 py-1.5 text-center">
                              {s.nsg_id ? "✓" : <span className="text-gray-300">—</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          ))}
        </Section>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 6 — DELIVERABLES                                       */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {engagement.deliverables.length > 0 && (
        <Section id="deliverables" altBg>
          <SectionHeader>5. Deliverables</SectionHeader>
          <ul className="divide-y divide-gray-200">
            {engagement.deliverables.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-gray-900">{d.title}</p>
                  <p className="text-xs text-gray-400">
                    {d.type.replace(/_/g, " ")} · {new Date(d.createdAt).toLocaleDateString()}
                  </p>
                </div>
                {d.publishedAt ? (
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                    Published
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">Draft</span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SECTION 7 — DOCUMENTS                                          */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {engagement.documents.length > 0 && (
        <Section id="documents">
          <SectionHeader>6. Reference Documents</SectionHeader>
          <ul className="divide-y divide-gray-100">
            {engagement.documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between py-2">
                <p className="text-sm text-gray-800">{doc.fileName}</p>
                <span className="text-xs text-gray-400">
                  {doc.docType.replace(/_/g, " ")} · {new Date(doc.createdAt).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* Footer */}
      <div className="mt-8 border-t border-gray-200 pt-4 text-center text-xs text-gray-400 print:mt-4">
        Generated by CNA Platform · {date}
      </div>
    </div>
  );
}

// ── Layout primitives ─────────────────────────────────────────────────────────

function Section({
  id,
  altBg,
  children,
}: {
  id: string;
  altBg?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className={`rounded-xl border border-gray-200 p-6 shadow-sm print:break-inside-avoid ${altBg ? "bg-gray-50" : "bg-white"}`}
    >
      {children}
    </section>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 text-lg font-bold text-gray-900 border-b border-gray-100 pb-2">
      {children}
    </h2>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg bg-white border border-gray-100 px-4 py-3 text-center shadow-sm">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}
