"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

export async function createEngagement(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) {
    redirect("/auth/signin");
  }

  const name = (formData.get("name") as string | null)?.trim() ?? "";
  const clientOrg = (formData.get("clientOrg") as string | null)?.trim() ?? "";

  if (!name || !clientOrg) {
    throw new Error("Engagement name and client organization are required.");
  }

  const engagement = await prisma.engagement.create({
    data: {
      name,
      clientOrg,
      members: {
        create: {
          userId: session.user.id,
          role: "ADMIN",
        },
      },
    },
  });

  revalidatePath("/dashboard");
  redirect(`/engagements/${engagement.id}`);
}

export async function deleteEngagement(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) {
    redirect("/auth/signin");
  }

  const engagementId = (formData.get("engagementId") as string | null)?.trim();
  if (!engagementId) return;

  // Only members may delete.
  const member = await prisma.engagementMember.findUnique({
    where: {
      engagementId_userId: { engagementId, userId: session.user.id },
    },
  });
  if (!member) return;

  await prisma.engagement.delete({ where: { id: engagementId } });

  revalidatePath("/dashboard");
  redirect("/dashboard");
}
