import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { publishDeliverable } from "./actions";
import { GenerateDeliverableForm } from "./generate-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

const DELIVERABLE_TEMPLATES = [
  {
    type: "EXECUTIVE_SUMMARY",
    label: "Executive Summary",
    icon: "📋",
    desc: "High-level overview for leadership: finding counts by severity, top risks, and business impact summary. No technical jargon.",
    sections: ["Finding severity breakdown", "Top 3 risks", "Business impact", "Recommended next steps"],
    audience: "CxO, CISO, Board",
  },
  {
    type: "TECHNICAL_FINDINGS",
    label: "Technical Findings Report",
    icon: "🔍",
    desc: "Full engineering report: every finding grouped by severity and category, with detailed descriptions and remediation steps.",
    sections: ["All findings by severity", "Detailed descriptions", "Remediation guidance", "Resource references"],
    audience: "Security Engineer, Network Architect",
  },
  {
    type: "REMEDIATION_PLAN",
    label: "Remediation Plan",
    icon: "🛠️",
    desc: "Ordered task list: findings sorted by priority with specific remediation steps and estimated effort.",
    sections: ["Prioritized task list", "Remediation steps", "Effort estimates", "Dependencies"],
    audience: "IT / Platform team",
  },
  {
    type: "SPECIALIZATION_REPORT",
    label: "Specialization Report",
    icon: "🏗️",
    desc: "Deep-dive on a specific domain such as Zero Trust, compliance (NIST/CIS), or connectivity architecture.",
    sections: ["Domain-specific findings", "Framework mapping", "Gap analysis", "Roadmap recommendations"],
    audience: "Security Architect, Compliance team",
  },
];

export default async function DeliverablesPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: {
      id: true,
      members: true,
      deliverables: { orderBy: { createdAt: "desc" } },
      findings: { select: { id: true } },
    },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  const { deliverables, findings } = engagement;
  const hasFindngs = findings.length > 0;

  return (
    <div className="space-y-6">
      {/* ── Generated deliverables list ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Generated Deliverables
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Reports generated from your findings data. Publish when reviewed to
          mark the engagement as delivered.
        </p>

        {deliverables.length === 0 ? (
          <p className="mb-4 text-sm text-gray-400">
            No deliverables yet. Generate one from a template below.
          </p>
        ) : (
          <ul className="mb-6 divide-y divide-gray-100">
            {deliverables.map((d) => {
              const template = DELIVERABLE_TEMPLATES.find(
                (t) => t.type === d.type,
              );
              return (
                <li key={d.id} className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{template?.icon ?? "📄"}</span>
                        <p className="text-sm font-semibold text-gray-900">
                          {d.title}
                        </p>
                        {d.publishedAt && (
                          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                            Published
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 ml-7 text-xs text-gray-400">
                        {d.type.replace(/_/g, " ")} ·{" "}
                        {new Date(d.createdAt).toLocaleString()}
                        {d.publishedAt &&
                          ` · Published ${new Date(d.publishedAt).toLocaleDateString()}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {!d.publishedAt && (
                        <form action={publishDeliverable}>
                          <input
                            type="hidden"
                            name="deliverableId"
                            value={d.id}
                          />
                          <input
                            type="hidden"
                            name="engagementId"
                            value={id}
                          />
                          <button
                            type="submit"
                            className="rounded-lg border border-green-600 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-50"
                          >
                            Publish
                          </button>
                        </form>
                      )}
                    </div>
                  </div>
                  {d.content && (
                    <details className="ml-7 mt-3">
                      <summary className="cursor-pointer text-xs text-blue-600 hover:underline">
                        Preview content
                      </summary>
                      <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-gray-50 p-4 text-xs text-gray-700 whitespace-pre-wrap">
                        {d.content}
                      </pre>
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ── Generate new deliverable ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Generate Deliverable
        </h2>
        {!hasFindngs && (
          <div className="mb-4 rounded-lg bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            No findings yet — run discovery or AI analysis first to populate the
            data that will be included in deliverables.
          </div>
        )}
        <GenerateDeliverableForm engagementId={id} />
      </section>

      {/* ── Deliverable templates reference ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Deliverable Templates
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Each report type serves a distinct audience. Reference the table below
          when deciding which deliverable to generate.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {DELIVERABLE_TEMPLATES.map((t) => (
            <div
              key={t.type}
              className="rounded-lg border border-gray-200 p-4"
            >
              <div className="mb-2 flex items-center gap-2">
                <span className="text-xl">{t.icon}</span>
                <p className="text-sm font-semibold text-gray-900">
                  {t.label}
                </p>
              </div>
              <p className="mb-3 text-xs text-gray-500">{t.desc}</p>
              <div className="mb-2">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                  Sections
                </p>
                <ul className="mt-1 space-y-0.5">
                  {t.sections.map((s) => (
                    <li key={s} className="text-xs text-gray-600">
                      · {s}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="text-xs text-gray-400">
                <span className="font-semibold">Audience:</span> {t.audience}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
