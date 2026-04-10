import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { DeleteEngagementButton } from "@/components/ui/delete-engagement-button";
import { EngagementSidebar } from "@/components/ui/engagement-sidebar";

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
    <div className="flex min-h-[calc(100vh-4rem)] flex-col">
      {/* ── Top header bar ── */}
      <div className="mb-4 flex items-start justify-between border-b border-gray-200 pb-4">
        <div>
          <Link
            href="/dashboard"
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            ← Back to dashboard
          </Link>
          <div className="mt-1.5 flex items-center gap-3">
            <h1 className="text-xl font-semibold text-gray-900">
              {engagement.name}
            </h1>
            <StatusBadge value={engagement.status} variant="status" />
          </div>
          <p className="text-sm text-gray-500">{engagement.clientOrg}</p>
        </div>
        <DeleteEngagementButton
          engagementId={id}
          engagementName={engagement.name}
          variant="header"
        />
      </div>

      {/* ── Sidebar + content ── */}
      <div className="flex flex-1 items-start gap-4">
        <EngagementSidebar engagementId={id} />
        <main className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
