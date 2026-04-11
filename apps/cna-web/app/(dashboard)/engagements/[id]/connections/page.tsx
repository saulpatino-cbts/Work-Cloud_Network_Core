import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { CredentialForm } from "../cloud-credentials/credential-form";
import { ConnectionsPanel } from "./connections-panel";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ConnectionsPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: { id: true, members: true },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  let credentials: Awaited<ReturnType<typeof prisma.cloudCredential.findMany>> = [];
  let jobs: Awaited<ReturnType<typeof prisma.discoveryJob.findMany>> = [];

  try {
    [credentials, jobs] = await Promise.all([
      prisma.cloudCredential.findMany({
        where: { engagementId: id },
        orderBy: { createdAt: "asc" },
      }),
      prisma.discoveryJob.findMany({
        where: { engagementId: id },
        orderBy: { createdAt: "desc" },
        take: 50,
      }),
    ]);
  } catch {
    // migration pending
  }

  const jobsForPanel = jobs.map((j) => ({
    id: j.id,
    status: j.status,
    startedAt: j.startedAt,
    completedAt: j.completedAt,
    findingsCount: j.findingsCount,
    errorMessage: j.errorMessage,
    progressLog: j.progressLog,
    credentialId: j.credentialId,
  }));

  return (
    <div className="space-y-6">
      {/* ── Cloud connections ── */}
      <section className="glass p-6">
        <h2 className="mb-1 text-lg font-semibold text-navy-100">
          Cloud Connections
        </h2>
        <p className="mb-5 text-sm text-navy-400">
          Connect to an Azure tenant via service principal. Each subscription
          becomes a separate credential entry for targeted discovery.
        </p>

        <ConnectionsPanel
          engagementId={id}
          credentials={credentials.map((c) => ({
            id: c.id,
            label: c.label,
            platform: c.platform,
            tenantId: c.tenantId,
            subscriptionIds: c.subscriptionIds,
          }))}
          jobs={jobsForPanel}
        />
      </section>

      {/* ── Add cloud connection ── */}
      <section className="glass p-6">
        <h2 className="mb-1 text-lg font-semibold text-navy-100">
          Add Cloud Connection
        </h2>
        <p className="mb-4 text-sm text-navy-400">
          Provide Azure service principal credentials and upload or enter
          subscription IDs. Auth credentials are encrypted at rest.
        </p>
        <CredentialForm engagementId={id} />
      </section>
    </div>
  );
}
