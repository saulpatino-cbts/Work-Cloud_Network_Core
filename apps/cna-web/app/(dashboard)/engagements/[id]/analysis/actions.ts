"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { analyzeDocuments } from "@/lib/openai";
import { revalidatePath } from "next/cache";

export async function runAnalysis(
  _prev: { error?: string; success?: boolean; count?: number } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean; count?: number }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  if (!engagementId) return { error: "Missing engagement ID." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const documents = await prisma.ingestedDocument.findMany({
    where: { engagementId, parsedText: { not: null } },
    select: { fileName: true, parsedText: true },
  });

  if (documents.length === 0) {
    return {
      error:
        "No analyzable documents found. Upload text-based files (CSV, TXT, JSON, YAML) first.",
    };
  }

  const rawFindings = await analyzeDocuments(
    documents.map((d) => ({ fileName: d.fileName, text: d.parsedText! })),
  );

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
