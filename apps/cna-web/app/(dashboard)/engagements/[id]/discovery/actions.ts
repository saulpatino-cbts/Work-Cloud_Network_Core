"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { decrypt } from "@/lib/crypto";
import { revalidatePath } from "next/cache";

export async function startAllDiscovery(
  engagementId: string,
): Promise<{ error?: string; started?: number }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const credentials = await prisma.cloudCredential.findMany({
    where: { engagementId },
  });
  if (!credentials.length) return { error: "No credentials configured." };

  const apiUrl = process.env.CNA_API_INTERNAL_URL;
  if (!apiUrl) return { error: "Discovery API is not configured." };

  // Fire one independent job per credential so each subscription gets its own
  // progress bar, log, run count, and completion timestamp. The inventory merge
  // on the Inventory page reads the latest topology per credentialId, so
  // independent jobs compose correctly into the full multi-subscription view.
  let started = 0;
  for (const cred of credentials) {
    const job = await prisma.discoveryJob.create({
      data: { engagementId, credentialId: cred.id, status: "QUEUED" },
    });
    const spSecret = cred.spSecretEnc ? decrypt(cred.spSecretEnc) : null;
    try {
      const res = await fetch(`${apiUrl}/discovery/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: job.id,
          engagement_id: engagementId,
          credential_id: cred.id,
          tenant_id: cred.tenantId,
          subscription_ids: cred.subscriptionIds,
          sp_client_id: cred.spClientId,
          sp_client_secret: spSecret,
        }),
      });
      if (!res.ok) {
        await prisma.discoveryJob.update({
          where: { id: job.id },
          data: { status: "FAILED", errorMessage: `API error ${res.status}` },
        });
      } else {
        started++;
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      await prisma.discoveryJob.update({
        where: { id: job.id },
        data: { status: "FAILED", errorMessage: message },
      });
    }
  }

  revalidatePath(`/engagements/${engagementId}`);
  return { started };
}

export async function startDiscovery(
  _prev: { error?: string; jobId?: string } | null,
  formData: FormData,
): Promise<{ error?: string; jobId?: string }> {
  const session = await auth();
  if (!session?.user?.id) return { error: "Not authenticated." };

  const engagementId = formData.get("engagementId") as string | null;
  const credentialId = formData.get("credentialId") as string | null;
  if (!engagementId || !credentialId) return { error: "Missing parameters." };

  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return { error: "Access denied." };

  const cred = await prisma.cloudCredential.findUnique({
    where: { id: credentialId },
  });
  if (!cred || cred.engagementId !== engagementId) return { error: "Credential not found." };

  // Create the job record in QUEUED state first so the UI can show it immediately.
  const job = await prisma.discoveryJob.create({
    data: { engagementId, credentialId, status: "QUEUED" },
  });

  // Hand off to cna-api which will run discovery in a background task.
  const apiUrl = process.env.CNA_API_INTERNAL_URL;
  if (!apiUrl) {
    await prisma.discoveryJob.update({
      where: { id: job.id },
      data: { status: "FAILED", errorMessage: "CNA_API_INTERNAL_URL is not configured." },
    });
    return { error: "Discovery API is not configured." };
  }

  const spSecret = cred.spSecretEnc ? decrypt(cred.spSecretEnc) : null;

  try {
    const res = await fetch(`${apiUrl}/discovery/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: job.id,
        engagement_id: engagementId,
        credential_id: cred.id,
        tenant_id: cred.tenantId,
        subscription_ids: cred.subscriptionIds,
        sp_client_id: cred.spClientId,
        sp_client_secret: spSecret,
      }),
    });

    if (!res.ok) {
      const body = await res.text();
      await prisma.discoveryJob.update({
        where: { id: job.id },
        data: { status: "FAILED", errorMessage: `API error ${res.status}: ${body.slice(0, 300)}` },
      });
      return { error: "Failed to start discovery. Check API logs." };
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    await prisma.discoveryJob.update({
      where: { id: job.id },
      data: { status: "FAILED", errorMessage: message },
    });
    return { error: `Could not reach discovery API: ${message}` };
  }

  revalidatePath(`/engagements/${engagementId}`);
  return { jobId: job.id };
}
