"use server";

import { auth } from "@/lib/auth";
import { uploadEngagementFile } from "@/lib/blob";
import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";
import type { DeliverableType, DocumentType } from "@prisma/client";

type ActionResult = { error?: string; success?: boolean };

function sanitizeFileName(fileName: string): string {
  return fileName.replace(/[^a-zA-Z0-9._-]/g, "_");
}

async function ensureMembership(engagementId: string, userId: string): Promise<boolean> {
  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId } },
    select: { id: true },
  });
  return !!member;
}

export async function saveDiagramSource(
  _prev: ActionResult | null,
  formData: FormData,
): Promise<ActionResult> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const file = formData.get("sourceFile") as File | null;
  if (!engagementId || !file || file.size === 0) return { error: "Diagram file is required." };

  const isMember = await ensureMembership(engagementId, session.user.id);
  if (!isMember) return { error: "Access denied." };

  const lower = file.name.toLowerCase();
  if (!(lower.endsWith(".drawio") || lower.endsWith(".xml"))) {
    return { error: "Only .drawio or .xml files are allowed for source diagrams." };
  }

  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);
  let parsedText: string;
  try {
    parsedText = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return { error: "Source diagram must be valid UTF-8 XML." };
  }

  const safeName = sanitizeFileName(file.name);
  const blobPath = await uploadEngagementFile(
    engagementId,
    `diagrams/${Date.now()}-${safeName}`,
    buffer,
    file.type || "application/xml",
  );

  await prisma.ingestedDocument.create({
    data: {
      engagementId,
      fileName: file.name,
      blobPath,
      docType: "NETWORK_DIAGRAM" as DocumentType,
      parsedText,
    },
  });

  await prisma.engagement.updateMany({
    where: { id: engagementId, status: "DRAFT" },
    data: { status: "DISCOVERY" },
  });

  revalidatePath(`/engagements/${engagementId}/diagram`);
  revalidatePath(`/engagements/${engagementId}/documents`);
  return { success: true };
}

export async function uploadDiagramExport(
  _prev: ActionResult | null,
  formData: FormData,
): Promise<ActionResult> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const file = formData.get("exportFile") as File | null;
  const addToDeliverables = formData.get("addToDeliverables") === "on";
  if (!engagementId || !file || file.size === 0) return { error: "Export file is required." };

  const isMember = await ensureMembership(engagementId, session.user.id);
  if (!isMember) return { error: "Access denied." };

  const lower = file.name.toLowerCase();
  const allowed = [".png", ".svg", ".pdf"];
  if (!allowed.some((ext) => lower.endsWith(ext))) {
    return { error: "Export must be .png, .svg, or .pdf." };
  }

  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);
  const safeName = sanitizeFileName(file.name);
  const blobPath = await uploadEngagementFile(
    engagementId,
    `diagram-exports/${Date.now()}-${safeName}`,
    buffer,
    file.type || "application/octet-stream",
  );

  await prisma.ingestedDocument.create({
    data: {
      engagementId,
      fileName: file.name,
      blobPath,
      docType: "NETWORK_DIAGRAM" as DocumentType,
      parsedText: null,
    },
  });

  if (addToDeliverables) {
    const engagement = await prisma.engagement.findUnique({
      where: { id: engagementId },
      select: { clientOrg: true },
    });

    const date = new Date().toISOString().slice(0, 10);
    await prisma.deliverable.create({
      data: {
        engagementId,
        title: `${engagement?.clientOrg ?? "Client"} — Network Diagram Export — ${date}`,
        type: "SPECIALIZATION_REPORT" as DeliverableType,
        blobPath,
      },
    });
  }

  revalidatePath(`/engagements/${engagementId}/diagram`);
  revalidatePath(`/engagements/${engagementId}/documents`);
  revalidatePath(`/engagements/${engagementId}/deliverables`);
  revalidatePath(`/engagements/${engagementId}/client-deliverables`);
  return { success: true };
}
