import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";

interface PageProps {
  params: Promise<{ id: string }>;
}

const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];

export default async function EngagementOverviewPage({ params }: PageProps) {
  const { id } = await params;

  const base = await prisma.engagement.findUnique({
    where: { id },
    include: {
      members: { include: { user: true } },
      findings: { select: { severity: true, aiGenerated: true } },
      deliverables: {
        orderBy: { createdAt: "desc" },
        select: { id: true, title: true, type: true, publishedAt: true, createdAt: true },
      },
      documents: { select: { id: true } },
    },
  });
  if (!base) notFound();

  let jobSummary: { status: string; completedAt: Date | null; findingsCount: number | null } | null =
    null;
  try {
    jobSummary = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { status: true, completedAt: true, findingsCount: true },
    });
  } catch {
    // table not migrated yet
  }

  const bySev = Object.fromEntries(
    SEV_ORDER.map((s) => [s, base.findings.filter((f) => f.severity === s).length]),
  );
  const liveCount = base.findings.filter((f) => !f.aiGenerated).length;
  const aiCount = base.findings.filter((f) => f.aiGenerated).length;

  const PHASE_STEPS = [
    { key: "DRAFT", label: "Draft" },
    { key: "DISCOVERY", label: "Discovery" },
    { key: "ANALYSIS", label: "Analysis" },
    { key: "REVIEW", label: "Review" },
    { key: "DELIVERED", label: "Delivered" },
  ];
  const currentPhaseIdx = PHASE_STEPS.findIndex((p) => p.key === base.status);

  return (
    <div className="space-y-6">
      {/* ── Phase progress bar ── */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Engagement Progress
        </h2>
        <div className="flex items-center gap-0">
          {PHASE_STEPS.map((step, idx) => {
            const done = idx < currentPhaseIdx;
            const active = idx === currentPhaseIdx;
            return (
              <div key={step.key} className="flex flex-1 items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={[
                      "flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold",
                      done
                        ? "bg-green-500 text-white"
                        : active
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-400",
                    ].join(" ")}
                  >
                    {done ? "✓" : idx + 1}
                  </div>
                  <span
                    className={[
                      "mt-1 text-xs",
                      active ? "font-semibold text-blue-600" : "text-gray-400",
                    ].join(" ")}
                  >
                    {step.label}
                  </span>
                </div>
                {idx < PHASE_STEPS.length - 1 && (
                  <div
                    className={[
                      "mb-5 h-0.5 flex-1",
                      idx < currentPhaseIdx ? "bg-green-400" : "bg-gray-200",
                    ].join(" ")}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Stats grid ── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Total findings"
          value={base.findings.length}
          href={`/engagements/${id}/findings`}
          color="blue"
        />
        <StatCard
          label="Documents"
          value={base.documents.length}
          href={`/engagements/${id}/documents`}
          color="indigo"
        />
        <StatCard
          label="Deliverables"
          value={base.deliverables.length}
          href={`/engagements/${id}/deliverables`}
          color="purple"
        />
        <StatCard
          label="Discovery runs"
          value={jobSummary ? "Completed" : "Not run"}
          href={`/engagements/${id}/connections`}
          color={jobSummary ? "green" : "gray"}
          small
        />
      </div>

      {/* ── Findings severity breakdown ── */}
      {base.findings.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Findings Breakdown
            </h2>
            <Link
              href={`/engagements/${id}/findings`}
              className="text-xs text-blue-600 hover:underline"
            >
              View all →
            </Link>
          </div>
          <div className="flex gap-3">
            {SEV_ORDER.map((sev) =>
              bySev[sev] > 0 ? (
                <div
                  key={sev}
                  className="flex flex-1 flex-col items-center rounded-lg bg-gray-50 py-3"
                >
                  <StatusBadge value={sev} variant="severity" />
                  <span className="mt-2 text-xl font-bold text-gray-900">
                    {bySev[sev]}
                  </span>
                </div>
              ) : null,
            )}
          </div>
          <div className="mt-3 flex gap-4 text-xs text-gray-500">
            <span>{liveCount} from live discovery</span>
            <span>{aiCount} from AI analysis</span>
          </div>
        </div>
      )}

      {/* ── Latest deliverables ── */}
      {base.deliverables.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Latest Deliverables
            </h2>
            <Link
              href={`/engagements/${id}/deliverables`}
              className="text-xs text-blue-600 hover:underline"
            >
              View all →
            </Link>
          </div>
          <ul className="divide-y divide-gray-100">
            {base.deliverables.slice(0, 3).map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-gray-900">{d.title}</p>
                  <p className="text-xs text-gray-400">
                    {d.type.replace(/_/g, " ")} ·{" "}
                    {new Date(d.createdAt).toLocaleDateString()}
                  </p>
                </div>
                {d.publishedAt ? (
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                    Published
                  </span>
                ) : (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                    Draft
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Quick links ── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {[
          { label: "Manage Connections", desc: "Add cloud credentials and run discovery", href: `/engagements/${id}/connections` },
          { label: "View Findings", desc: "Security findings matrix and AI analysis", href: `/engagements/${id}/findings` },
          { label: "Network Inventory", desc: "All discovered resources, NSGs, and IPs", href: `/engagements/${id}/inventory` },
          { label: "Documents", desc: "Upload reference documents and templates", href: `/engagements/${id}/documents` },
          { label: "Deliverables", desc: "Generate and publish assessment reports", href: `/engagements/${id}/deliverables` },
          { label: "Presentation", desc: "Interactive static report view", href: `/engagements/${id}/presentation` },
        ].map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <p className="text-sm font-semibold text-gray-900">{item.label}</p>
            <p className="mt-1 text-xs text-gray-500">{item.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  href,
  color,
  small,
}: {
  label: string;
  value: number | string;
  href: string;
  color: "blue" | "indigo" | "purple" | "green" | "gray";
  small?: boolean;
}) {
  const colors = {
    blue: "bg-blue-50 text-blue-700",
    indigo: "bg-indigo-50 text-indigo-700",
    purple: "bg-purple-50 text-purple-700",
    green: "bg-green-50 text-green-700",
    gray: "bg-gray-50 text-gray-500",
  };
  return (
    <Link
      href={href}
      className={`rounded-xl border border-gray-100 p-4 shadow-sm transition-shadow hover:shadow-md ${colors[color]}`}
    >
      <p className={`font-bold ${small ? "text-lg" : "text-3xl"}`}>{value}</p>
      <p className="mt-1 text-xs font-medium">{label}</p>
    </Link>
  );
}
