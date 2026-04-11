"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { uploadDeliverable } from "@/lib/blob";
import { generateDeliverableContent } from "@/lib/openai";
import { revalidatePath } from "next/cache";
import type { DeliverableType } from "@prisma/client";

// ─── Server Actions ───────────────────────────────────────────────────────────

export async function generateDeliverable(
  _prev: { error?: string; success?: boolean } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const type = formData.get("type") as string | null;
  const title = (formData.get("title") as string | null)?.trim() ?? "";
  const customerLogoUrl = (formData.get("customerLogoUrl") as string | null) ?? null;

  if (!engagementId || !type || !title) {
    return { error: "All fields are required." };
  }

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  // Gather all context sources in parallel
  const [engagement, findings, documents, latestJob] = await Promise.all([
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
  ]);

  if (!engagement) return { error: "Engagement not found." };
  if (findings.length === 0) {
    return {
      error:
        "No findings yet. Run discovery and/or AI analysis before generating deliverables.",
    };
  }

  const content = await generateDeliverableContent({
    type: type as DeliverableType,
    title,
    clientOrg: engagement.clientOrg,
    engagementName: engagement.name,
    findings,
    topologyJson: latestJob?.topologyJson ?? null,
    documents: documents.map((d) => ({ fileName: d.fileName, text: d.parsedText! })),
    customerLogoUrl,
  });

  const fileName = `${type.toLowerCase()}-${Date.now()}.md`;
  const blobPath = await uploadDeliverable(engagementId, fileName, content);

  await prisma.deliverable.create({
    data: {
      engagementId,
      title,
      type: type as DeliverableType,
      blobPath,
      content,
    },
  });

  await prisma.engagement.update({
    where: { id: engagementId },
    data: { status: "REVIEW" },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true };
}

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
