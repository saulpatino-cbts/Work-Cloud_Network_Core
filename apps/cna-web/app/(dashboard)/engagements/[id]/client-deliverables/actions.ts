"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";

// Create a single INTERACTIVE_ASSESSMENT deliverable record (replaces existing if present)
export async function createInteractiveAssessment(
  engagementId: string,
): Promise<{ error?: string; success?: boolean }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  // Delete any existing interactive assessment for this engagement (one at a time)
  await prisma.deliverable.deleteMany({
    where: { engagementId, type: "INTERACTIVE_ASSESSMENT" },
  });

  const engagement = await prisma.engagement.findUnique({
    where: { id: engagementId },
    select: { clientOrg: true, name: true },
  });
  if (!engagement) return { error: "Engagement not found." };

  const date = new Date().toISOString().split("T")[0];
  await prisma.deliverable.create({
    data: {
      engagementId,
      type: "INTERACTIVE_ASSESSMENT",
      title: `${engagement.clientOrg} — Interactive Assessment — ${date}`,
      publishedAt: new Date(),
      publishedBy: session.user.id,
    },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true };
}

// Delete a deliverable (any type) — canonical delete used from client-deliverables page
export async function deleteDeliverableFromPortal(formData: FormData) {
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

// Delete an uploaded document
export async function deleteDocument(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) return;

  const documentId = formData.get("documentId") as string | null;
  const engagementId = formData.get("engagementId") as string | null;
  if (!documentId || !engagementId) return;

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return;

  await prisma.ingestedDocument.delete({ where: { id: documentId } });
  revalidatePath(`/engagements/${engagementId}`);
}
