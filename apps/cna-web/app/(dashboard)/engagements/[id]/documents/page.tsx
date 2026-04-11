import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { UploadDocumentForm } from "./upload-form";
import { ComplianceReportPanel } from "./compliance-report-panel";

interface PageProps {
  params: Promise<{ id: string }>;
}

// Templates in the user-specified order:
// Row 1: Azure Subscriptions, Firewall Policies
// Row 2: NSG Rules, Route Table
// Row 3: Network Architecture Notes (centered)
const TEMPLATES = [
  {
    name: "Azure Subscription Inventory.csv",
    desc: "List all subscriptions with IDs, names, and management group membership.",
    docType: "CONFIGURATION_EXPORT",
    columns: "subscription_id,subscription_name,tenant_id,management_group,state",
  },
  {
    name: "Firewall Policy Rules.csv",
    desc: "Document firewall rule collections — application and network rules.",
    docType: "CONFIGURATION_EXPORT",
    columns: "rule_collection,priority,rule_name,source,destination,protocol,ports,action",
  },
  {
    name: "NSG Rule Export.csv",
    desc: "Export NSG rules per subnet — source, destination, port, action.",
    docType: "CONFIGURATION_EXPORT",
    columns: "nsg_name,resource_group,subnet,priority,direction,protocol,source,destination,destination_port,action",
  },
  {
    name: "Route Table Export.csv",
    desc: "Custom route table entries — destination CIDR, next hop type, next hop IP.",
    docType: "CONFIGURATION_EXPORT",
    columns: "route_table_name,resource_group,route_name,address_prefix,next_hop_type,next_hop_ip_address",
  },
  {
    name: "Network Architecture Notes.txt",
    desc: "Free-form architecture notes: hub-spoke topology, connectivity model, key segments.",
    docType: "CLIENT_ARCHITECTURE",
    columns: null,
    centered: true,
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

  // Check if we have topology data for Generate buttons
  let hasTopology = false;
  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      select: { id: true },
    });
    hasTopology = !!job;
  } catch { /* migration pending */ }

  return (
    <div className="space-y-6">
      {/* ── Uploaded documents ── */}
      <section className="glass p-6">
        <h2 className="mb-1 text-lg font-semibold text-navy-100">
          Uploaded Documents
        </h2>
        <p className="mb-5 text-sm text-navy-400">
          Secondary source — upload compliance frameworks, architecture notes,
          NSG exports, or route tables. Text files are parsed for AI analysis.
        </p>

        {engagement.documents.length === 0 ? (
          <p className="mb-4 text-sm text-navy-500">No documents uploaded yet.</p>
        ) : (
          <ul className="mb-6 divide-y divide-navy-700/30">
            {engagement.documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-navy-100">{doc.fileName}</p>
                  <p className="text-xs text-navy-400">
                    {new Date(doc.createdAt).toLocaleString()}
                    {doc.parsedText
                      ? " · text extracted — ready for AI analysis"
                      : " · binary — stored as-is"}
                  </p>
                </div>
                <StatusBadge value={doc.docType} variant="doctype" />
              </li>
            ))}
          </ul>
        )}

        <div className="border-t border-navy-700/30 pt-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-300">Upload document</h3>
          <UploadDocumentForm engagementId={id} />
        </div>
      </section>

      {/* ── Compliance Check ── */}
      <ComplianceReportPanel engagementId={id} hasTopology={hasTopology} />

      {/* ── Document templates ── */}
      <section className="glass p-6">
        <h2 className="mb-1 text-lg font-semibold text-navy-100">
          Document Templates
        </h2>
        <p className="mb-5 text-sm text-navy-400">
          Download a pre-structured template, fill it in with data from the
          customer environment, then upload it above for AI analysis.
        </p>

        {/* Row 1: Azure Subscriptions + Firewall Policies */}
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          {TEMPLATES.slice(0, 2).map((t) => (
            <TemplateCard key={t.name} t={t} engagementId={id} hasTopology={hasTopology} />
          ))}
        </div>

        {/* Row 2: NSG Rules + Route Table */}
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          {TEMPLATES.slice(2, 4).map((t) => (
            <TemplateCard key={t.name} t={t} engagementId={id} hasTopology={hasTopology} />
          ))}
        </div>

        {/* Row 3: Network Architecture Notes — centered */}
        <div className="flex justify-center">
          <div className="w-full sm:w-1/2">
            <TemplateCard t={TEMPLATES[4]} engagementId={id} hasTopology={hasTopology} />
          </div>
        </div>
      </section>
    </div>
  );
}

// ─── Template card ─────────────────────────────────────────────────────────────

function TemplateCard({
  t,
  engagementId,
  hasTopology,
}: {
  t: (typeof TEMPLATES)[0];
  engagementId: string;
  hasTopology: boolean;
}) {
  const content = t.columns
    ? `${t.columns}\n# Fill in rows below this comment line — delete this line before uploading\n`
    : `# ${t.name.replace(/\.[^.]+$/, "")}\n\n${t.desc}\n\n# Add your notes below:\n\n`;

  const encoded = Buffer.from(content).toString("base64");
  const mime = t.columns ? "text/csv" : "text/plain";
  const isCsv = !!t.columns;

  return (
    <div className="flex flex-col justify-between rounded-xl border border-navy-700/40 bg-navy-800/20 p-4">
      <div>
        <div className="mb-1 flex items-center gap-2">
          <p className="text-sm font-semibold text-navy-100">{t.name}</p>
          <StatusBadge value={t.docType} variant="doctype" />
        </div>
        <p className="text-xs text-navy-400">{t.desc}</p>
        {t.columns && (
          <p className="mt-2 break-all overflow-hidden rounded border border-navy-700/40 bg-navy-900/40 px-2 py-1 font-mono text-xs text-navy-300">
            {t.columns}
          </p>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href={`data:${mime};base64,${encoded}`}
          download={t.name}
          className="inline-flex items-center gap-1.5 rounded-lg border border-navy-600/60 bg-navy-700/40 px-3 py-1.5 text-xs font-medium text-navy-200 hover:bg-navy-700/60 transition-colors"
        >
          ↓ Download template
        </a>
        {isCsv && hasTopology && (
          <GenerateFromTopologyButton
            engagementId={engagementId}
            templateName={t.name}
          />
        )}
      </div>
    </div>
  );
}

// ─── Generate from topology (client component placeholder) ────────────────────
// This renders a link to the generate API route

function GenerateFromTopologyButton({
  engagementId,
  templateName,
}: {
  engagementId: string;
  templateName: string;
}) {
  return (
    <a
      href={`/api/generate-csv?engagementId=${engagementId}&template=${encodeURIComponent(templateName)}`}
      download={templateName}
      className="inline-flex items-center gap-1.5 rounded-lg border border-teal-700/60 bg-teal-900/30 px-3 py-1.5 text-xs font-medium text-teal-300 hover:bg-teal-900/50 transition-colors"
    >
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      Generate from live data
    </a>
  );
}
