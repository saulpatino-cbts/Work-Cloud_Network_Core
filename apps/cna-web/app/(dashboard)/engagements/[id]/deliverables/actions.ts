"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { uploadDeliverable } from "@/lib/blob";
import { revalidatePath } from "next/cache";
import type { DeliverableType, Engagement, Finding } from "@prisma/client";

// ─── Report builder ───────────────────────────────────────────────────────────

function buildReport(
  type: string,
  title: string,
  engagement: Engagement,
  findings: Finding[],
): string {
  const date = new Date().toISOString().split("T")[0];
  const bySev = (sev: string) => findings.filter((f) => f.severity === sev);
  const SEVERITIES = [
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFORMATIONAL",
  ] as const;

  const lines: string[] = [
    `# ${title}`,
    ``,
    `**Client:** ${engagement.clientOrg}  `,
    `**Engagement:** ${engagement.name}  `,
    `**Date:** ${date}  `,
    `**Type:** ${type.replace(/_/g, " ")}`,
    ``,
    `---`,
    ``,
  ];

  if (type === "EXECUTIVE_SUMMARY") {
    lines.push(
      `## Executive Summary`,
      ``,
      `This Cloud Network Assessment identified **${findings.length} findings** across the ${engagement.clientOrg} environment.`,
      ``,
      `| Severity | Count |`,
      `|----------|-------|`,
      ...SEVERITIES.map((s) => `| ${s} | ${bySev(s).length} |`),
      ``,
    );
  } else if (type === "TECHNICAL_FINDINGS" || type === "SPECIALIZATION_REPORT") {
    lines.push(`## Findings`, ``);
    for (const sev of SEVERITIES) {
      const group = bySev(sev);
      if (!group.length) continue;
      lines.push(`### ${sev}`, ``);
      for (const f of group) {
        lines.push(
          `#### ${f.title}`,
          ``,
          `**Category:** ${f.category}  `,
          `**Severity:** ${f.severity}`,
          ``,
          f.description,
          ``,
          `**Recommendation:** ${f.recommendation ?? "Review and address the identified issue."}`,
          ``,
        );
      }
    }
  } else if (type === "REMEDIATION_PLAN") {
    lines.push(`## Remediation Plan`, ``);
    let i = 1;
    for (const sev of SEVERITIES) {
      for (const f of bySev(sev)) {
        lines.push(
          `### ${i++}. ${f.title} (${f.severity})`,
          ``,
          f.recommendation ?? "Review and address the identified issue.",
          ``,
        );
      }
    }
  }

  return lines.join("\n");
}

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

  if (!engagementId || !type || !title) {
    return { error: "All fields are required." };
  }

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const [engagement, findings] = await Promise.all([
    prisma.engagement.findUnique({ where: { id: engagementId } }),
    prisma.finding.findMany({
      where: { engagementId },
      orderBy: [{ severity: "asc" }, { createdAt: "asc" }],
    }),
  ]);

  if (!engagement) return { error: "Engagement not found." };

  const content = buildReport(type, title, engagement, findings);
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
