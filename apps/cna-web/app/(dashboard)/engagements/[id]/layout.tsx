import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { DeleteEngagementButton } from "@/components/ui/delete-engagement-button";
import { EngagementTabs } from "@/components/ui/engagement-tabs";

interface LayoutProps {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}

export default async function EngagementLayout({
  children,
  params,
}: LayoutProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    include: { members: true },
  });

  if (!engagement) notFound();

  const isMember = engagement.members.some(
    (m) => m.userId === session?.user?.id,
  );
  if (!isMember) notFound();

  return (
    <div className="space-y-0">
      {/* ── Header ── */}
      <div className="mb-6 flex items-start justify-between">
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
        <DeleteEngagementButton
          engagementId={id}
          engagementName={engagement.name}
          variant="header"
        />
      </div>

      {/* ── Tab navigation ── */}
      <EngagementTabs engagementId={id} />

      {/* ── Page content ── */}
      <div className="mt-6">{children}</div>
    </div>
  );
}
