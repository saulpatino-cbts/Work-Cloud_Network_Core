"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { uploadDeliverable } from "@/lib/blob";
import { generateDeliverableContent } from "@/lib/openai";
import type { DeliverableType as OpenAIDeliverableType } from "@/lib/openai";
import { revalidatePath } from "next/cache";
import type { DeliverableType } from "@prisma/client";

const TYPE_LABELS: Record<string, string> = {
  COMPREHENSIVE_ASSESSMENT: "Comprehensive Assessment",
  EXECUTIVE_SUMMARY: "Executive Summary",
  TECHNICAL_FINDINGS: "Technical Findings",
  REMEDIATION_PLAN: "Remediation Plan",
  SPECIALIZATION_REPORT: "Specialization Report",
};

const ALL_TYPES: OpenAIDeliverableType[] = [
  "COMPREHENSIVE_ASSESSMENT",
  "EXECUTIVE_SUMMARY",
  "TECHNICAL_FINDINGS",
  "REMEDIATION_PLAN",
  "SPECIALIZATION_REPORT",
];

function buildTitle(type: string, clientOrg: string, seqNum: number): string {
  const label = TYPE_LABELS[type] ?? type.replace(/_/g, " ");
  const date = new Date().toISOString().split("T")[0];
  return `${clientOrg} — ${label} — ${date} — #${seqNum}`;
}

// ─── Generate single assessment ───────────────────────────────────────────────

export async function generateDeliverable(
  _prev: { error?: string; success?: boolean } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const type = formData.get("type") as string | null;
  const customerLogoUrl = (formData.get("customerLogoUrl") as string | null) ?? null;

  if (!engagementId || !type) return { error: "Missing required fields." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const [engagement, findings, documents, latestJob, existingCount] = await Promise.all([
    prisma.engagement.findUnique({ where: { id: engagementId } }),
    prisma.finding.findMany({
      where: { engagementId },
      orderBy: [{ severity: "asc" }, { createdAt: "asc" }],
    }),
    prisma.ingestedDocument.findMany({
      where: { engagementId, parsedText: { not: null } },
      select: { fileName: true, parsedText: true },
    }),
    prisma.discoveryJob
      .findFirst({
        where: { engagementId, status: "COMPLETED" },
        orderBy: { completedAt: "desc" },
        select: { topologyJson: true },
      })
      .catch(() => null),
    prisma.deliverable.count({ where: { engagementId } }),
  ]);

  if (!engagement) return { error: "Engagement not found." };
  if (findings.length === 0) {
    return { error: "No findings yet. Run discovery and/or AI analysis before generating assessments." };
  }

  const title = buildTitle(type, engagement.clientOrg, existingCount + 1);

  let content: string;
  try {
    content = await generateDeliverableContent({
      type: type as OpenAIDeliverableType,
      title,
      clientOrg: engagement.clientOrg,
      engagementName: engagement.name,
      findings,
      topologyJson: latestJob?.topologyJson ?? null,
      documents: documents.map((d) => ({ fileName: d.fileName, text: d.parsedText! })),
      customerLogoUrl,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("401") || msg.includes("PermissionDenied") || msg.includes("lacks the required")) {
      return { error: "AI generation failed: the web app is missing the 'Cognitive Services OpenAI User' role on the Azure OpenAI resource." };
    }
    return { error: `AI generation failed: ${msg.slice(0, 200)}` };
  }

  const ext = type === "COMPREHENSIVE_ASSESSMENT" ? "html" : "md";
  const fileName = `${type.toLowerCase()}-${Date.now()}.${ext}`;
  const blobPath = await uploadDeliverable(engagementId, fileName, content);

  await prisma.deliverable.create({
    data: { engagementId, title, type: type as DeliverableType, blobPath, content },
  });

  await prisma.engagement.update({
    where: { id: engagementId },
    data: { status: "REVIEW" },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true };
}

// ─── Generate all assessment types ────────────────────────────────────────────

export async function generateAllAssessments(
  _prev: { error?: string; success?: boolean; count?: number } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean; count?: number }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const customerLogoUrl = (formData.get("customerLogoUrl") as string | null) ?? null;
  if (!engagementId) return { error: "Missing engagement ID." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const [engagement, findings, documents, latestJob, existingCount] = await Promise.all([
    prisma.engagement.findUnique({ where: { id: engagementId } }),
    prisma.finding.findMany({
      where: { engagementId },
      orderBy: [{ severity: "asc" }, { createdAt: "asc" }],
    }),
    prisma.ingestedDocument.findMany({
      where: { engagementId, parsedText: { not: null } },
      select: { fileName: true, parsedText: true },
    }),
    prisma.discoveryJob
      .findFirst({
        where: { engagementId, status: "COMPLETED" },
        orderBy: { completedAt: "desc" },
        select: { topologyJson: true },
      })
      .catch(() => null),
    prisma.deliverable.count({ where: { engagementId } }),
  ]);

  if (!engagement) return { error: "Engagement not found." };
  if (findings.length === 0) {
    return { error: "No findings yet. Run discovery and/or AI analysis before generating assessments." };
  }

  const docInput = documents.map((d) => ({ fileName: d.fileName, text: d.parsedText! }));
  const topologyJson = latestJob?.topologyJson ?? null;

  const settled = await Promise.allSettled(
    ALL_TYPES.map((type, i) =>
      generateDeliverableContent({
        type,
        title: buildTitle(type, engagement.clientOrg, existingCount + i + 1),
        clientOrg: engagement.clientOrg,
        engagementName: engagement.name,
        findings,
        topologyJson,
        documents: docInput,
        customerLogoUrl,
      }).then((content) => ({ type, content })),
    ),
  );

  let saved = 0;
  for (const result of settled) {
    if (result.status !== "fulfilled") continue;
    const { type, content } = result.value;
    const ext = type === "COMPREHENSIVE_ASSESSMENT" ? "html" : "md";
    const fileName = `${type.toLowerCase()}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}.${ext}`;
    try {
      const blobPath = await uploadDeliverable(engagementId, fileName, content);
      const title = buildTitle(type, engagement.clientOrg, existingCount + saved + 1);
      await prisma.deliverable.create({
        data: { engagementId, title, type, blobPath, content },
      });
      saved++;
    } catch { /* skip failed saves */ }
  }

  const failed = settled.filter((r) => r.status === "rejected").length;
  if (failed > 0 && saved === 0) {
    return { error: `All ${failed} assessment generations failed. Check Azure OpenAI connectivity.` };
  }

  await prisma.engagement.update({
    where: { id: engagementId },
    data: { status: "REVIEW" },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true, count: saved };
}

// ─── Delete assessment ─────────────────────────────────────────────────────────

export async function deleteDeliverable(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) return;

  const deliverableId = formData.get("deliverableId") as string | null;
  const engagementId = formData.get("engagementId") as string | null;
  if (!deliverableId || !engagementId) return;

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return;

  await prisma.deliverable.delete({ where: { id: deliverableId } });
  revalidatePath(`/engagements/${engagementId}`);
}

// ─── Publish assessment ────────────────────────────────────────────────────────

export async function publishDeliverable(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) return;

  const deliverableId = formData.get("deliverableId") as string | null;
  const engagementId = formData.get("engagementId") as string | null;
  if (!deliverableId || !engagementId) return;

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return;

  await prisma.deliverable.update({
    where: { id: deliverableId },
    data: { publishedAt: new Date(), publishedBy: session.user.id },
  });

  await prisma.engagement.update({
    where: { id: engagementId },
    data: { status: "DELIVERED" },
  });

  revalidatePath(`/engagements/${engagementId}`);
}
