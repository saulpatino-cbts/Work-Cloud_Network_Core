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

const MAX_DIAGRAM_XML_BYTES = 5 * 1024 * 1024;

/**
 * Persists diagram XML sent by the embedded draw.io editor (its Save button /
 * Ctrl+S). Each save is a new blob + IngestedDocument version; a single
 * Deliverable entry per engagement is upserted to always point at the latest.
 */
export async function saveDiagramXml(
  engagementId: string,
  xml: string,
): Promise<ActionResult> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };
  if (!engagementId) return { error: "Engagement is required." };

  const isMember = await ensureMembership(engagementId, session.user.id);
  if (!isMember) return { error: "Access denied." };

  const trimmed = xml?.trim() ?? "";
  if (!trimmed) return { error: "Diagram is empty — nothing to save." };
  if (!/^<(\?xml|mxfile|mxGraphModel)/.test(trimmed)) {
    return { error: "Unexpected diagram payload; expected draw.io XML." };
  }
  const buffer = Buffer.from(trimmed, "utf-8");
  if (buffer.byteLength > MAX_DIAGRAM_XML_BYTES) {
    return { error: "Diagram exceeds the 5 MB save limit." };
  }

  const fileName = `editor-${new Date().toISOString().slice(0, 10)}.drawio`;
  const blobPath = await uploadEngagementFile(
    engagementId,
    `diagrams/${Date.now()}-${sanitizeFileName(fileName)}`,
    buffer,
    "application/xml",
  );

  await prisma.ingestedDocument.create({
    data: {
      engagementId,
      fileName,
      blobPath,
      docType: "NETWORK_DIAGRAM" as DocumentType,
      parsedText: trimmed,
    },
  });

  // Surface the diagram in Deliverables: one entry per engagement, always
  // pointing at the most recent save.
  const engagement = await prisma.engagement.findUnique({
    where: { id: engagementId },
    select: { clientOrg: true },
  });
  const title = `${engagement?.clientOrg ?? "Client"} — Network Diagram (draw.io)`;
  const existing = await prisma.deliverable.findFirst({
    where: { engagementId, title },
    select: { id: true },
  });
  if (existing) {
    await prisma.deliverable.update({ where: { id: existing.id }, data: { blobPath } });
  } else {
    await prisma.deliverable.create({
      data: {
        engagementId,
        title,
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
