"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { analyzeEngagement, type AnalysisFocus } from "@/lib/openai";
import { revalidatePath } from "next/cache";

export async function runAnalysis(
  _prev: { error?: string; success?: boolean; count?: number } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean; count?: number }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const focus = (formData.get("focus") as AnalysisFocus | null) ?? "general";
  if (!engagementId) return { error: "Missing engagement ID." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  // Gather all three data sources in parallel
  const [documents, existingFindings, latestJob] = await Promise.all([
    prisma.ingestedDocument.findMany({
      where: { engagementId, parsedText: { not: null } },
      select: { fileName: true, parsedText: true },
    }),
    prisma.finding.findMany({
      where: { engagementId },
      select: { title: true, severity: true, category: true, description: true },
    }),
    prisma.discoveryJob
      .findFirst({
        where: { engagementId, status: "COMPLETED" },
        orderBy: { completedAt: "desc" },
        select: { topologyJson: true },
      })
      .catch(() => null), // table may not be migrated in all envs
  ]);

  const hasTopology = !!latestJob?.topologyJson;
  const hasDocs = documents.length > 0;

  if (!hasTopology && !hasDocs) {
    return {
      error:
        "No data to analyze. Run a discovery first to capture topology, or upload network documents.",
    };
  }

  const rawFindings = await analyzeEngagement({
    topologyJson: latestJob?.topologyJson ?? null,
    documents: documents.map((d) => ({ fileName: d.fileName, text: d.parsedText! })),
    existingFindings,
    focus,
  });

  if (rawFindings.length > 0) {
    await prisma.finding.createMany({
      data: rawFindings.map((f) => ({
        engagementId,
        title: f.title,
        severity: f.severity,
        category: f.category,
        description: f.description,
        recommendation: f.recommendation,
        aiGenerated: true,
      })),
    });
  }

  await prisma.engagement.update({
    where: { id: engagementId },
    data: { status: "ANALYSIS" },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true, count: rawFindings.length };
}
