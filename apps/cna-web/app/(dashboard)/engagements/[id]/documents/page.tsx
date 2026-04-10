import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { UploadDocumentForm } from "./upload-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

// Document templates — files the analyst knows will always be useful
const TEMPLATES = [
  {
    name: "Azure Subscription Inventory.csv",
    desc: "List all subscriptions with IDs, names, and management group membership.",
    docType: "CONFIGURATION_EXPORT",
    columns: "subscription_id,subscription_name,tenant_id,management_group,state",
  },
  {
    name: "NSG Rule Export.csv",
    desc: "Export NSG rules per subnet — source, destination, port, action.",
    docType: "CONFIGURATION_EXPORT",
    columns: "nsg_name,resource_group,subnet,priority,direction,protocol,source,destination,destination_port,action",
  },
  {
    name: "Firewall Policy Rules.csv",
    desc: "Document firewall rule collections — application and network rules.",
    docType: "CONFIGURATION_EXPORT",
    columns: "rule_collection,priority,rule_name,source,destination,protocol,ports,action",
  },
  {
    name: "Network Architecture Notes.txt",
    desc: "Free-form architecture notes: hub-spoke topology, connectivity model, key segments.",
    docType: "CLIENT_ARCHITECTURE",
    columns: null,
  },
  {
    name: "Compliance Requirements.txt",
    desc: "List compliance frameworks in scope (PCI-DSS, HIPAA, SOC2, NIST, etc.) with relevant controls.",
    docType: "COMPLIANCE_FRAMEWORK",
    columns: null,
  },
  {
    name: "Route Table Export.csv",
    desc: "Custom route table entries — destination CIDR, next hop type, next hop IP.",
    docType: "CONFIGURATION_EXPORT",
    columns: "route_table_name,resource_group,route_name,address_prefix,next_hop_type,next_hop_ip_address",
  },
];

export default async function DocumentsPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: {
      id: true,
      members: true,
      documents: { orderBy: { createdAt: "desc" } },
    },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  return (
    <div className="space-y-6">
      {/* ── Uploaded documents ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Uploaded Documents
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Secondary source — upload compliance frameworks, architecture notes,
          NSG exports, or route tables. Text files are parsed for AI analysis.
        </p>

        {engagement.documents.length === 0 ? (
          <p className="mb-4 text-sm text-gray-400">
            No documents uploaded yet.
          </p>
        ) : (
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
                    {doc.parsedText ? " · text extracted — ready for AI analysis" : " · binary — stored as-is"}
                  </p>
                </div>
                <StatusBadge value={doc.docType} variant="doctype" />
              </li>
            ))}
          </ul>
        )}

        <div className="border-t border-gray-100 pt-5">
          <h3 className="mb-3 text-sm font-semibold text-gray-700">
            Upload document
          </h3>
          <UploadDocumentForm engagementId={id} />
        </div>
      </section>

      {/* ── Document templates ── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">
          Document Templates
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Download a pre-structured template, fill it in with data from the
          customer environment, then upload it above for AI analysis.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {TEMPLATES.map((t) => (
            <div
              key={t.name}
              className="flex flex-col justify-between rounded-lg border border-gray-200 p-4"
            >
              <div>
                <div className="mb-1 flex items-center gap-2">
                  <p className="text-sm font-semibold text-gray-900">
                    {t.name}
                  </p>
                  <StatusBadge value={t.docType} variant="doctype" />
                </div>
                <p className="text-xs text-gray-500">{t.desc}</p>
                {t.columns && (
                  <p className="mt-2 rounded bg-gray-50 px-2 py-1 font-mono text-xs text-gray-600">
                    {t.columns}
                  </p>
                )}
              </div>
              <TemplateDownloadButton
                fileName={t.name}
                columns={t.columns}
                isText={!t.columns}
                desc={t.desc}
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// Rendered server-side — generates a data-URI download in the browser via JS
function TemplateDownloadButton({
  fileName,
  columns,
  isText,
  desc,
}: {
  fileName: string;
  columns: string | null;
  isText: boolean;
  desc: string;
}) {
  const content = isText
    ? `# ${fileName.replace(/\.[^.]+$/, "")}\n\n${desc}\n\n# Add your notes below:\n\n`
    : `${columns}\n# Fill in rows below this comment line — delete this line before uploading\n`;

  const encoded = Buffer.from(content).toString("base64");
  const mime = isText ? "text/plain" : "text/csv";

  return (
    <a
      href={`data:${mime};base64,${encoded}`}
      download={fileName}
      className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
    >
      ↓ Download template
    </a>
  );
}
