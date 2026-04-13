import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ClientDeliverablesPage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    select: { members: true },
  });
  if (!engagement) notFound();

  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  return (
    <div className="glass flex min-h-[40vh] flex-col items-center justify-center rounded-xl p-12 text-center">
      <svg
        className="mb-4 h-12 w-12 text-navy-500"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
        />
      </svg>
      <h2 className="text-lg font-semibold text-navy-300">Client Deliverables</h2>
      <p className="mt-2 text-sm text-navy-500">Coming soon — this section will host packaged deliverables for client hand-off.</p>
    </div>
  );
}
