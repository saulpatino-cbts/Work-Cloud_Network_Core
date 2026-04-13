import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { AiAnalysisForm } from "../findings/ai-analysis-form";
import { ComplianceReportPanel } from "../documents/compliance-report-panel";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function AnalysisPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: { id: true, members: true },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  let hasTopology = false;
  let hasDocumentsParsed = false;
  try {
    const [job, docCount] = await Promise.all([
      prisma.discoveryJob.findFirst({
        where: { engagementId: id, status: "COMPLETED" },
        select: { id: true },
      }),
      prisma.ingestedDocument.count({
        where: { engagementId: id, parsedText: { not: null } },
      }),
    ]);
    hasTopology = !!job;
    hasDocumentsParsed = docCount > 0;
  } catch { /* migration pending */ }

  const hasAnalysisData = hasTopology || hasDocumentsParsed;

  return (
    <div className="space-y-6">
      {/* ── AI Analysis ── */}
      <section className="glass p-6">
        <h2 className="mb-1 text-lg font-semibold text-navy-100">AI Analysis</h2>
        <p className="mb-4 text-sm text-navy-400">
          Run a focused security analysis on your discovered topology and uploaded
          documents. Each focus type uses a different analytical lens. Results are
          added to the Findings tab.
        </p>
        {!hasAnalysisData ? (
          <p className="rounded-lg border border-amber-800/40 bg-amber-900/20 px-4 py-3 text-sm text-amber-400">
            No data to analyze yet. Run discovery on the Connections tab to capture live
            topology, or upload documents on the Documents tab.
          </p>
        ) : (
          <AiAnalysisForm engagementId={id} />
        )}
      </section>

      {/* ── Compliance Check ── */}
      <ComplianceReportPanel engagementId={id} hasTopology={hasTopology} />
    </div>
  );
}
