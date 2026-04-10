import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { deleteCloudCredential } from "../cloud-credentials/actions";
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
        take: 20,
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
      {/* ── Subscriptions / credentials ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Cloud Connections
        </h2>
        <p className="mb-5 text-sm text-gray-500">
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

        {/* Remove buttons row */}
        {credentials.length > 0 && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
              Remove subscription
            </p>
            <div className="flex flex-wrap gap-2">
              {credentials.map((cred) => (
                <form key={cred.id} action={deleteCloudCredential}>
                  <input type="hidden" name="credentialId" value={cred.id} />
                  <input type="hidden" name="engagementId" value={id} />
                  <button
                    type="submit"
                    className="flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-100"
                  >
                    <span>✕</span>
                    <span>{cred.label}</span>
                  </button>
                </form>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ── Add cloud connection ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Add Cloud Connection
        </h2>
        <p className="mb-4 text-sm text-gray-500">
          Provide Azure service principal credentials and upload or enter
          subscription IDs. Auth credentials are encrypted at rest.
        </p>
        <CredentialForm engagementId={id} />
      </section>
    </div>
  );
}
