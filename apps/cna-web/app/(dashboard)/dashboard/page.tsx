import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";

export default async function DashboardPage() {
  const session = await auth();

  // Load the user's engagements from the database.
  const engagements = await prisma.engagement.findMany({
    where: {
      members: {
        some: { userId: session!.user!.id! },
      },
    },
    include: {
      _count: { select: { findings: true, documents: true } },
    },
    orderBy: { updatedAt: "desc" },
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Engagements</h1>
          <p className="mt-1 text-sm text-gray-500">
            Active and recent network assessment engagements
          </p>
        </div>
        <Link
          href="/engagements/new"
          className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          + New engagement
        </Link>
      </div>

      {engagements.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <p className="text-sm text-gray-500">No engagements yet.</p>
          <p className="mt-1 text-xs text-gray-400">
            Create an engagement to start a Cloud Network Assessment.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {engagements.map((eng) => (
            <li key={eng.id}>
              <Link
                href={`/engagements/${eng.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:border-blue-300 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{eng.name}</p>
                    <p className="text-sm text-gray-500">{eng.clientOrg}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-xs text-gray-400">
                      <p>{eng._count.documents} documents</p>
                      <p>{eng._count.findings} findings</p>
                    </div>
                    <StatusBadge value={eng.status} variant="status" />
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
