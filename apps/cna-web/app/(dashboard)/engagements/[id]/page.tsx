import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { CredentialForm } from "./cloud-credentials/credential-form";
import { deleteCloudCredential } from "./cloud-credentials/actions";
import { DiscoveryPanel } from "./discovery/discovery-panel";
import { UploadDocumentForm } from "./documents/upload-form";
import { RunAnalysisForm } from "./analysis/run-form";
import { GenerateDeliverableForm } from "./deliverables/generate-form";
import { publishDeliverable } from "./deliverables/actions";
import { DeleteEngagementButton } from "@/components/ui/delete-engagement-button";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function EngagementPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  // Base query — always works regardless of migration state.
  const base = await prisma.engagement.findUnique({
    where: { id },
    include: {
      members: { include: { user: true } },
      documents: { orderBy: { createdAt: "desc" } },
      findings: { orderBy: [{ severity: "asc" }, { createdAt: "asc" }] },
      deliverables: { orderBy: { createdAt: "desc" } },
    },
  });

  if (!base) notFound();

  const isMember = base.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  // Discovery tables may not exist yet if the migration is pending.
  // Fail open with empty arrays so the page renders while the DB is being migrated.
  let cloudCredentials: Awaited<ReturnType<typeof prisma.cloudCredential.findMany>> = [];
  let rawJobs: Awaited<ReturnType<typeof prisma.discoveryJob.findMany>> = [];
  try {
    [cloudCredentials, rawJobs] = await Promise.all([
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
    // Tables not yet migrated — render the page with empty discovery state.
  }

  const jobsForPanel = rawJobs.map((j) => ({
    id: j.id,
    status: j.status,
    startedAt: j.startedAt,
    completedAt: j.completedAt,
    findingsCount: j.findingsCount,
    errorMessage: j.errorMessage,
    progressLog: j.progressLog,
    credentialId: j.credentialId,
  }));

  const liveFindings = base.findings.filter((f) => !f.aiGenerated);
  const aiFindings = base.findings.filter((f) => f.aiGenerated);

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/dashboard"
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            ← Back to dashboard
          </Link>
          <div className="mt-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-gray-900">
              {base.name}
            </h1>
            <StatusBadge value={base.status} variant="status" />
          </div>
          <p className="mt-1 text-sm text-gray-500">{base.clientOrg}</p>
        </div>

        {/* Delete engagement */}
        <DeleteEngagementButton
          engagementId={id}
          engagementName={base.name}
          variant="header"
        />
      </div>

      {/* ── Cloud Connections ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Cloud Connections
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Connect directly to an Azure tenant to discover live network topology.
          This is the primary source of truth — document upload is secondary.
        </p>

        <DiscoveryPanel
          engagementId={id}
          credentials={cloudCredentials}
          jobs={jobsForPanel}
        />

        {cloudCredentials.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-3">
            {cloudCredentials.map((cred) => (
              <form key={cred.id} action={deleteCloudCredential}>
                <input type="hidden" name="credentialId" value={cred.id} />
                <input type="hidden" name="engagementId" value={id} />
                <button
                  type="submit"
                  className="text-xs text-gray-400 hover:text-red-600"
                >
                  Remove "{cred.label}"
                </button>
              </form>
            ))}
          </div>
        )}

        <div className="mt-6 border-t border-gray-100 pt-5">
          <h3 className="mb-3 text-sm font-medium text-gray-700">
            Add cloud connection
          </h3>
          <CredentialForm engagementId={id} />
        </div>
      </section>

      {/* ── Findings ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Findings
            {base.findings.length > 0 && (
              <span className="ml-1 text-base font-normal text-gray-500">
                ({base.findings.length})
              </span>
            )}
          </h2>
          <RunAnalysisForm engagementId={id} />
        </div>

        {base.findings.length === 0 ? (
          <p className="text-sm text-gray-400">
            No findings yet. Run discovery against a live tenant, or upload
            documents and run AI analysis.
          </p>
        ) : (
          <>
            {liveFindings.length > 0 && (
              <div className="mb-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
                  From live discovery ({liveFindings.length})
                </p>
                <FindingList findings={liveFindings} />
              </div>
            )}
            {aiFindings.length > 0 && (
              <div>
                {liveFindings.length > 0 && (
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
                    From document analysis ({aiFindings.length})
                  </p>
                )}
                <FindingList findings={aiFindings} />
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Documents ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">Documents</h2>
        <p className="mb-4 text-sm text-gray-500">
          Secondary source — upload compliance frameworks, architecture diagrams,
          or configuration exports that can&apos;t be auto-discovered.
        </p>

        {base.documents.length > 0 ? (
          <ul className="mb-6 divide-y divide-gray-100">
            {base.documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between py-3"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {doc.fileName}
                  </p>
                  <p className="text-xs text-gray-400">
                    {new Date(doc.createdAt).toLocaleString()}
                    {doc.parsedText ? " · text extracted" : ""}
                  </p>
                </div>
                <StatusBadge value={doc.docType} variant="doctype" />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-6 text-sm text-gray-400">No documents yet.</p>
        )}

        <div className="border-t border-gray-100 pt-5">
          <h3 className="mb-3 text-sm font-medium text-gray-700">
            Upload document
          </h3>
          <UploadDocumentForm engagementId={id} />
        </div>
      </section>

      {/* ── Deliverables ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Deliverables
        </h2>

        {base.deliverables.length > 0 ? (
          <ul className="mb-6 divide-y divide-gray-100">
            {base.deliverables.map((d) => (
              <li key={d.id} className="py-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {d.title}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {d.type.replace(/_/g, " ")} ·{" "}
                      {new Date(d.createdAt).toLocaleDateString()}
                      {d.publishedAt
                        ? ` · Published ${new Date(d.publishedAt).toLocaleDateString()}`
                        : ""}
                    </p>
                  </div>
                  {!d.publishedAt && (
                    <form action={publishDeliverable}>
                      <input type="hidden" name="deliverableId" value={d.id} />
                      <input type="hidden" name="engagementId" value={id} />
                      <button
                        type="submit"
                        className="rounded-lg border border-green-600 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-50"
                      >
                        Publish
                      </button>
                    </form>
                  )}
                </div>
                {d.content && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-xs text-blue-600 hover:underline">
                      Preview
                    </summary>
                    <pre className="mt-2 overflow-auto rounded-lg bg-gray-50 p-4 text-xs text-gray-700 whitespace-pre-wrap">
                      {d.content}
                    </pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-6 text-sm text-gray-400">
            No deliverables yet. Generate one after running analysis.
          </p>
        )}

        <div className="border-t border-gray-100 pt-5">
          <h3 className="mb-3 text-sm font-medium text-gray-700">
            Generate deliverable
          </h3>
          <GenerateDeliverableForm engagementId={id} />
        </div>
      </section>
    </div>
  );
}

function FindingList({
  findings,
}: {
  findings: {
    id: string;
    title: string;
    category: string;
    description: string;
    recommendation: string | null;
    severity: string;
  }[];
}) {
  return (
    <ul className="divide-y divide-gray-100">
      {findings.map((f) => (
        <li key={f.id} className="py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-900">{f.title}</p>
              <p className="mt-0.5 text-xs text-gray-500">{f.category}</p>
              <p className="mt-2 text-sm text-gray-700">{f.description}</p>
              {f.recommendation && (
                <p className="mt-2 text-xs text-gray-500">
                  <span className="font-medium">Recommendation:</span>{" "}
                  {f.recommendation}
                </p>
              )}
            </div>
            <div className="shrink-0">
              <StatusBadge value={f.severity} variant="severity" />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
