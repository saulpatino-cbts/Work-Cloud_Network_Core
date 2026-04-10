import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { UploadDocumentForm } from "./documents/upload-form";
import { RunAnalysisForm } from "./analysis/run-form";
import { GenerateDeliverableForm } from "./deliverables/generate-form";
import { publishDeliverable } from "./deliverables/actions";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function EngagementPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    include: {
      members: { include: { user: true } },
      documents: { orderBy: { createdAt: "desc" } },
      findings: { orderBy: [{ severity: "asc" }, { createdAt: "asc" }] },
      deliverables: { orderBy: { createdAt: "desc" } },
    },
  });

  if (!engagement) notFound();

  const isMember = engagement.members.some(
    (m) => m.userId === session?.user?.id,
  );
  if (!isMember) notFound();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link
          href="/dashboard"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← Back to dashboard
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-gray-900">
            {engagement.name}
          </h1>
          <StatusBadge value={engagement.status} variant="status" />
        </div>
        <p className="mt-1 text-sm text-gray-500">{engagement.clientOrg}</p>
      </div>

      {/* Documents */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Documents</h2>

        {engagement.documents.length > 0 ? (
          <ul className="mb-6 divide-y divide-gray-100">
            {engagement.documents.map((doc) => (
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

      {/* Findings */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Findings{" "}
            {engagement.findings.length > 0 && (
              <span className="ml-1 text-base font-normal text-gray-500">
                ({engagement.findings.length})
              </span>
            )}
          </h2>
          <RunAnalysisForm engagementId={id} />
        </div>

        {engagement.findings.length > 0 ? (
          <ul className="divide-y divide-gray-100">
            {engagement.findings.map((f) => (
              <li key={f.id} className="py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900">
                      {f.title}
                    </p>
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
        ) : (
          <p className="text-sm text-gray-400">
            No findings yet. Run analysis to generate findings from uploaded
            documents.
          </p>
        )}
      </section>

      {/* Deliverables */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Deliverables
        </h2>

        {engagement.deliverables.length > 0 ? (
          <ul className="mb-6 divide-y divide-gray-100">
            {engagement.deliverables.map((d) => (
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
                      <input
                        type="hidden"
                        name="deliverableId"
                        value={d.id}
                      />
                      <input
                        type="hidden"
                        name="engagementId"
                        value={id}
                      />
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
