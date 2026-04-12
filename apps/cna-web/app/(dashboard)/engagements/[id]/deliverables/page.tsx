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
    type: "COMPREHENSIVE_ASSESSMENT",
    label: "Comprehensive Assessment",
    icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    desc: "Interactive HTML assessment covering all dimensions: architecture, security, compliance, resilience, cost. All findings included. Opens as a web page — print to PDF.",
    audience: "All Stakeholders",
  },
  {
    type: "EXECUTIVE_SUMMARY",
    label: "Executive Summary",
    icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    desc: "ALL risks in business language with impact per finding, severity breakdown, 30/60/90-day action roadmap.",
    audience: "CxO / CISO / Board",
  },
  {
    type: "TECHNICAL_FINDINGS",
    label: "Technical Findings",
    icon: "M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z",
    desc: "Every finding with root cause, Azure CLI remediation steps, NIST/CIS mapping, and MS Learn links.",
    audience: "Security Engineers / Architects",
  },
  {
    type: "REMEDIATION_PLAN",
    label: "Remediation Plan",
    icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
    desc: "Prioritized task list: numbered steps, validation checks, rollback procedures, effort estimates.",
    audience: "IT / Platform Team",
  },
  {
    type: "SPECIALIZATION_REPORT",
    label: "Specialization Report",
    icon: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
    desc: "Framework gap analysis (NIST/CIS/WAF), maturity scoring, compliance gap register, architecture recommendations.",
    audience: "Security Architect / Compliance",
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

  return (
    <div className="space-y-5">
      {/* ── Generated deliverables ── */}
      <div className="glass p-6">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="label-caps text-navy-300 dark:text-navy-500">Generated Deliverables</p>
            <p className="mt-0.5 text-xs text-navy-400 dark:text-navy-400">
              Review, then publish to mark the engagement as delivered.
            </p>
          </div>
          {deliverables.length > 0 && (
            <span className="pill-teal">{deliverables.length} report{deliverables.length !== 1 ? "s" : ""}</span>
          )}
        </div>

        {deliverables.length === 0 ? (
          <div className="rounded-xl border border-dashed border-navy-200 px-6 py-10 text-center dark:border-navy-700">
            <p className="text-sm font-medium text-navy-400 dark:text-navy-500">
              No deliverables yet
            </p>
            <p className="mt-1 text-xs text-navy-300 dark:text-navy-600">
              Generate one from the form below.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-navy-100/40 dark:divide-navy-700/40">
            {deliverables.map((d) => {
              const template = DELIVERABLE_TEMPLATES.find((t) => t.type === d.type);
              return (
                <div key={d.id} className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex min-w-0 flex-1 items-start gap-3">
                      {template && (
                        <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-900/30">
                          <svg className="h-4 w-4 text-teal-600 dark:text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d={template.icon} />
                          </svg>
                        </div>
                      )}
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">
                            {d.title}
                          </p>
                          {d.publishedAt ? (
                            <span className="pill-teal">Published</span>
                          ) : (
                            <span className="rounded-full border border-navy-100 bg-navy-50 px-2.5 py-0.5 text-xs font-semibold text-navy-400 dark:border-navy-700 dark:bg-navy-800/50 dark:text-navy-400">
                              Draft
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 text-xs text-navy-400 dark:text-navy-400">
                          {d.type.replace(/_/g, " ")} ·{" "}
                          {new Date(d.createdAt).toLocaleString()}
                          {d.publishedAt &&
                            ` · Published ${new Date(d.publishedAt).toLocaleDateString()}`}
                        </p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {/* View / download link */}
                      <a
                        href={`/api/deliverables/${d.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-navy-600/60 bg-navy-700/40 px-3 py-1.5 text-xs font-medium text-navy-200 transition-colors hover:bg-navy-700/60"
                      >
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                        {d.type === "COMPREHENSIVE_ASSESSMENT" ? "View / PDF" : "Download"}
                      </a>
                      {!d.publishedAt && (
                        <form action={publishDeliverable}>
                          <input type="hidden" name="deliverableId" value={d.id} />
                          <input type="hidden" name="engagementId" value={id} />
                          <button
                            type="submit"
                            className="rounded-lg border border-teal-500 px-3 py-1.5 text-xs font-semibold text-teal-600 transition-colors hover:bg-teal-50 dark:border-teal-600 dark:text-teal-400 dark:hover:bg-teal-900/30"
                          >
                            Publish
                          </button>
                        </form>
                      )}
                    </div>
                  </div>

                  {d.content && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-xs font-medium text-teal-600 hover:underline dark:text-teal-400">
                        Preview content
                      </summary>
                      <div className="mt-3 max-h-96 overflow-auto rounded-xl border border-navy-100/60 bg-navy-50/60 p-5 dark:border-navy-700/40 dark:bg-navy-900/40">
                        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-navy-700 dark:text-navy-200">
                          {d.content}
                        </pre>
                      </div>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Generate new deliverable ── */}
      <div className="glass p-6">
        <p className="label-caps mb-1 text-navy-300 dark:text-navy-500">Generate Deliverable</p>
        <p className="mb-5 text-xs text-navy-400 dark:text-navy-400">
          AI-powered generation using live topology, uploaded documents, and all findings.
          {findings.length === 0 && (
            <span className="ml-2 font-medium text-amber-600 dark:text-amber-400">
              No findings yet — run discovery or AI analysis first.
            </span>
          )}
        </p>
        <GenerateDeliverableForm engagementId={id} />
      </div>

      {/* ── Templates reference ── */}
      <div className="glass p-6">
        <p className="label-caps mb-4 text-navy-300 dark:text-navy-500">Report Types</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {DELIVERABLE_TEMPLATES.map((t) => (
            <div
              key={t.type}
              className="rounded-xl border border-navy-100/60 bg-white/30 p-4 dark:border-navy-700/40 dark:bg-navy-800/20"
            >
              <div className="mb-2 flex items-center gap-2.5">
                <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-900/30">
                  <svg className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={t.icon} />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">{t.label}</p>
                  <p className="text-xs text-teal-600 dark:text-teal-400">{t.audience}</p>
                </div>
              </div>
              <p className="text-xs text-navy-400 dark:text-navy-400">{t.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
