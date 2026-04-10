import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { AiAnalysisForm } from "./ai-analysis-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"] as const;
type Sev = typeof SEV_ORDER[number];

const SEV_BG: Record<Sev, string> = {
  CRITICAL: "bg-red-600",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-yellow-400",
  LOW: "bg-blue-400",
  INFORMATIONAL: "bg-gray-300",
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

  const hasDocuments = await prisma.ingestedDocument
    .count({ where: { engagementId: id, parsedText: { not: null } } })
    .catch(() => 0);

  return (
    <div className="space-y-6">
      {/* ── Summary bar ── */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Findings
              {findings.length > 0 && (
                <span className="ml-2 text-base font-normal text-gray-500">
                  ({findings.length} total)
                </span>
              )}
            </h2>
            <p className="mt-0.5 text-sm text-gray-500">
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
                  className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1"
                >
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${SEV_BG[sev]}`}
                  />
                  <span className="text-xs font-semibold text-gray-700">
                    {sev[0] + sev.slice(1).toLowerCase()}
                  </span>
                  <span className="text-xs text-gray-500">{bySev[sev]}</span>
                </div>
              ) : null,
            )}
          </div>
        </div>
      </div>

      {/* ── Risk matrix ── */}
      {findings.length > 0 && categories.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">
            Risk Matrix — Severity × Category
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr>
                  <th className="w-40 pb-2 text-left text-xs font-semibold text-gray-500">
                    Category
                  </th>
                  {SEV_ORDER.map((sev) => (
                    <th key={sev} className="pb-2 text-center font-semibold text-gray-500">
                      {sev[0] + sev.slice(1).toLowerCase()}
                    </th>
                  ))}
                  <th className="pb-2 text-center font-semibold text-gray-500">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {categories.map((cat) => {
                  const rowTotal = SEV_ORDER.reduce(
                    (s, sev) => s + matrix[cat][sev].length,
                    0,
                  );
                  return (
                    <tr key={cat} className="hover:bg-gray-50">
                      <td className="py-2 pr-4 text-xs font-medium text-gray-700">
                        {cat}
                      </td>
                      {SEV_ORDER.map((sev) => {
                        const count = matrix[cat][sev].length;
                        return (
                          <td key={sev} className="py-2 text-center">
                            {count > 0 ? (
                              <span
                                className={`inline-flex h-6 w-6 items-center justify-center rounded font-bold text-white ${SEV_BG[sev]}`}
                              >
                                {count}
                              </span>
                            ) : (
                              <span className="text-gray-200">—</span>
                            )}
                          </td>
                        );
                      })}
                      <td className="py-2 text-center font-semibold text-gray-700">
                        {rowTotal}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── AI analysis section ── */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">AI Analysis</h2>
            <p className="mt-0.5 text-sm text-gray-500">
              Run a focused analysis on your uploaded documents. Each analysis
              type uses a different lens — choose the one most relevant to the
              current engagement phase.
            </p>
          </div>
        </div>
        {hasDocuments === 0 ? (
          <p className="rounded-lg bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            No analyzable documents found. Upload text-based files (CSV, TXT,
            JSON, YAML) on the Documents tab first.
          </p>
        ) : (
          <AiAnalysisForm engagementId={id} />
        )}
      </div>

      {/* ── Findings list grouped by category ── */}
      {findings.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className="text-sm font-medium text-gray-500">No findings yet.</p>
          <p className="mt-1 text-xs text-gray-400">
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
            />
          )}
          {aiFindings.length > 0 && (
            <FindingGroup
              title="From AI Analysis"
              findings={aiFindings}
              categories={categories}
              matrix={matrix}
              sevOrder={SEV_ORDER}
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
}: {
  title: string;
  findings: Finding[];
  categories: string[];
  matrix: Record<string, Record<Sev, Finding[]>>;
  sevOrder: readonly Sev[];
}) {
  const relevantCategories = categories.filter((cat) =>
    findings.some((f) => f.category === cat),
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 px-5 py-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          {title}{" "}
          <span className="ml-1 font-normal text-gray-400">
            ({findings.length})
          </span>
        </h3>
      </div>
      <div className="divide-y divide-gray-100">
        {relevantCategories.map((cat) => {
          const catFindings = findings.filter((f) => f.category === cat);
          return (
            <div key={cat}>
              <div className="bg-gray-50 px-5 py-2">
                <span className="text-xs font-semibold text-gray-600">
                  {cat}
                </span>
              </div>
              <ul className="divide-y divide-gray-100">
                {sevOrder.map((sev) =>
                  catFindings
                    .filter((f) => f.severity === sev)
                    .map((f) => (
                      <li key={f.id} className="px-5 py-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-gray-900">
                              {f.title}
                            </p>
                            <p className="mt-2 text-sm text-gray-700">
                              {f.description}
                            </p>
                            {f.recommendation && (
                              <div className="mt-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">
                                <span className="font-semibold">
                                  Recommendation:{" "}
                                </span>
                                {f.recommendation}
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
