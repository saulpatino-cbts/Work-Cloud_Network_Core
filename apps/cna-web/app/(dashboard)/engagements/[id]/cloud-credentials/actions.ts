"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { encrypt, decrypt } from "@/lib/crypto";
import { revalidatePath } from "next/cache";

// ─── Add credential ───────────────────────────────────────────────────────────

export async function addCloudCredential(
  _prev: { error?: string; success?: boolean } | null,
  formData: FormData,
): Promise<{ error?: string; success?: boolean }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const label = (formData.get("label") as string | null)?.trim() ?? "";
  const tenantId = (formData.get("tenantId") as string | null)?.trim() ?? "";
  const subscriptionIdsRaw = (formData.get("subscriptionIds") as string | null)?.trim() ?? "";
  const spClientId = (formData.get("spClientId") as string | null)?.trim() ?? "";
  const spClientSecret = (formData.get("spClientSecret") as string | null)?.trim() ?? "";

  if (!engagementId || !label || !tenantId) {
    return { error: "Label and Tenant ID are required." };
  }
  if (!spClientId || !spClientSecret) {
    return { error: "Service Principal Client ID and Secret are required." };
  }

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const subscriptionIds = subscriptionIdsRaw
    ? subscriptionIdsRaw.split(",").map((s) => s.trim()).filter(Boolean)
    : [];

  const spSecretEnc = encrypt(spClientSecret);

  await prisma.cloudCredential.upsert({
    where: { engagementId_label: { engagementId, label } },
    create: {
      engagementId,
      platform: "AZURE",
      label,
      tenantId,
      subscriptionIds,
      spClientId,
      spSecretEnc,
    },
    update: {
      tenantId,
      subscriptionIds,
      spClientId,
      spSecretEnc,
    },
  });

  revalidatePath(`/engagements/${engagementId}`);
  return { success: true };
}

// ─── Delete credential ────────────────────────────────────────────────────────

export async function deleteCloudCredential(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) return;

  const credentialId = formData.get("credentialId") as string | null;
  const engagementId = formData.get("engagementId") as string | null;
  if (!credentialId || !engagementId) return;

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return;

  await prisma.cloudCredential.delete({ where: { id: credentialId } });
  revalidatePath(`/engagements/${engagementId}`);
}

// ─── Test Azure connection ────────────────────────────────────────────────────
// Called directly from a client component (not via form submission).

export async function testAzureConnection(params: {
  tenantId: string;
  spClientId: string;
  spClientSecret: string;
}): Promise<{ ok: boolean; subscriptions?: string[]; error?: string }> {
  const session = await auth();
  if (!session?.user?.id) return { ok: false, error: "Not authenticated." };

  const { tenantId, spClientId, spClientSecret } = params;
  if (!tenantId || !spClientId || !spClientSecret) {
    return { ok: false, error: "Tenant ID, Client ID, and Client Secret are all required." };
  }

  try {
    const { ClientSecretCredential } = await import("@azure/identity");
    const credential = new ClientSecretCredential(tenantId, spClientId, spClientSecret);
    const tokenResponse = await credential.getToken(
      "https://management.azure.com/.default",
    );

    const res = await fetch(
      "https://management.azure.com/subscriptions?api-version=2022-12-01",
      { headers: { Authorization: `Bearer ${tokenResponse.token}` } },
    );

    if (!res.ok) {
      const body = await res.text();
      return { ok: false, error: `ARM API ${res.status}: ${body.slice(0, 200)}` };
    }

    const data = (await res.json()) as {
      value?: { subscriptionId: string; displayName: string }[];
    };
    const subscriptions = (data.value ?? []).map(
      (s) => `${s.displayName} (${s.subscriptionId})`,
    );

    return { ok: true, subscriptions };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: message };
  }
}

// ─── Decrypt helper (used by discovery action) ───────────────────────────────

export async function getDecryptedCredential(credentialId: string, userId: string) {
  const cred = await prisma.cloudCredential.findUnique({
    where: { id: credentialId },
    include: { engagement: { include: { members: true } } },
  });
  if (!cred) return null;

  const isMember = cred.engagement.members.some((m) => m.userId === userId);
  if (!isMember) return null;

  return {
    ...cred,
    spSecret: cred.spSecretEnc ? decrypt(cred.spSecretEnc) : null,
  };
}
