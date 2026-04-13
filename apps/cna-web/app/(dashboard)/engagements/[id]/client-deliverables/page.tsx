import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

const TYPE_META: Record<string, { label: string; audience: string; iconPath: string }> = {
  COMPREHENSIVE_ASSESSMENT: {
    label: "Comprehensive Assessment",
    audience: "All Stakeholders",
    iconPath:
      "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  EXECUTIVE_SUMMARY: {
    label: "Executive Summary",
    audience: "CxO / CISO / Board",
    iconPath:
      "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
  TECHNICAL_FINDINGS: {
    label: "Technical Findings",
    audience: "Security Engineers",
    iconPath:
      "M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z",
  },
  REMEDIATION_PLAN: {
    label: "Remediation Plan",
    audience: "IT / Platform Team",
    iconPath:
      "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
  },
  SPECIALIZATION_REPORT: {
    label: "Specialization Report",
    audience: "Security Architect / Compliance",
    iconPath:
      "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
  },
};

export default async function ClientDeliverablesPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: {
      id: true,
      members: { select: { userId: true } },
      deliverables: {
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          title: true,
          type: true,
          content: true,
          publishedAt: true,
          createdAt: true,
        },
      },
    },
  });
  if (!engagement) notFound();

  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  const published = engagement.deliverables.filter((d) => d.publishedAt !== null);
  const pending = engagement.deliverables.filter((d) => d.publishedAt === null);

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="glass p-6">
        <h2 className="text-lg font-semibold text-navy-100">Client Deliverables</h2>
        <p className="mt-1 text-sm text-navy-400">
          Packaged assessment outputs ready for client hand-off. Each deliverable can be
          viewed in-browser and saved as a PDF.
        </p>
      </div>

      {/* ── Published deliverables ── */}
      {published.length > 0 ? (
        <section className="space-y-3">
          <p className="label-caps text-navy-300 dark:text-navy-500">
            Published — {published.length} deliverable{published.length !== 1 ? "s" : ""}
          </p>
          {published.map((d) => {
            const meta = TYPE_META[d.type] ?? {
              label: d.type.replace(/_/g, " "),
              audience: "General",
              iconPath:
                "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
            };
            return (
              <div
                key={d.id}
                className="glass flex items-center justify-between gap-4 p-5"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-900/30">
                    <svg
                      className="h-5 w-5 text-teal-600 dark:text-teal-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={1.5}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d={meta.iconPath} />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-navy-100">{d.title}</p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-navy-400">{meta.label}</span>
                      <span className="text-navy-600">·</span>
                      <span className="text-xs text-navy-400">Audience: {meta.audience}</span>
                      <span className="text-navy-600">·</span>
                      <span className="text-xs text-navy-400">
                        Published {new Date(d.publishedAt!).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-shrink-0 items-center gap-2">
                  {d.content ? (
                    <a
                      href={`/api/deliverables/${d.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-teal-500"
                    >
                      <svg
                        className="h-3.5 w-3.5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                        />
                      </svg>
                      View / Print
                    </a>
                  ) : (
                    <span className="rounded-lg border border-navy-700 px-3 py-1.5 text-xs font-semibold text-navy-400">
                      File only
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      ) : (
        <div className="glass flex min-h-[28vh] flex-col items-center justify-center rounded-xl p-10 text-center">
          <svg
            className="mb-4 h-10 w-10 text-navy-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <p className="font-semibold text-navy-300">No deliverables published yet</p>
          <p className="mt-1 text-sm text-navy-500">
            Deliverables will appear here once the CBTS team publishes them.
          </p>
        </div>
      )}

      {/* ── Drafts in preparation ── */}
      {pending.length > 0 && (
        <section className="space-y-2">
          <p className="label-caps text-navy-300 dark:text-navy-500">
            In preparation — {pending.length} draft{pending.length !== 1 ? "s" : ""}
          </p>
          <div className="glass p-4">
            <ul className="divide-y divide-navy-100/30 dark:divide-navy-700/30">
              {pending.map((d) => {
                const meta = TYPE_META[d.type];
                return (
                  <li key={d.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-navy-300">{d.title}</p>
                      <p className="text-xs text-navy-500">
                        {meta?.label ?? d.type.replace(/_/g, " ")} · Created{" "}
                        {new Date(d.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="flex-shrink-0 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-400">
                      Preparing
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      )}

      {/* ── Presentation link ── */}
      <div className="glass flex items-center justify-between gap-4 p-5">
        <div>
          <p className="font-semibold text-navy-100">Interactive Assessment</p>
          <p className="mt-0.5 text-sm text-navy-400">
            Browse the full findings, maturity analysis, and remediation roadmap online.
          </p>
        </div>
        <Link
          href={`/engagements/${id}/presentation`}
          className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-navy-700 px-4 py-2 text-sm font-semibold text-navy-200 transition-colors hover:border-teal-500/50 hover:text-teal-400"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8 13v-1m4 1v-3m4 3V8M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
            />
          </svg>
          Open Presentation
        </Link>
      </div>
    </div>
  );
}
