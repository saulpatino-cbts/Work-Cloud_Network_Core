"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { uploadEngagementFile } from "@/lib/blob";
import { revalidatePath } from "next/cache";
import type { DocumentType } from "@prisma/client";

export async function uploadDocument(
  _prev: { error?: string; success?: boolean } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const docType = formData.get("docType") as string | null;
  const file = formData.get("file") as File | null;

  if (!engagementId || !docType || !file || file.size === 0) {
    return { error: "All fields are required." };
  }

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);

  // Extract text for plain-text file types so AI analysis can use them.
  let parsedText: string | null = null;
  const ext = file.name.toLowerCase().split(".").pop();
  if (ext && ["csv", "txt", "json", "yaml", "yml"].includes(ext)) {
    parsedText = new TextDecoder().decode(bytes);
  }

  const blobPath = await uploadEngagementFile(
    engagementId,
    file.name,
    buffer,
    file.type || "application/octet-stream",
  );

  await prisma.ingestedDocument.create({
    data: {
      engagementId,
      fileName: file.name,
      blobPath,
      docType: docType as DocumentType,
      parsedText,
    },
  });

  // Advance status from DRAFT → DISCOVERY on first document upload.
  await prisma.engagement.updateMany({
    where: { id: engagementId, status: "DRAFT" },
    data: { status: "DISCOVERY" },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true };
}
