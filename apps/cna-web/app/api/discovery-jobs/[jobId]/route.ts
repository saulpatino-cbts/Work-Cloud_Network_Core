import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { jobId } = await params;

  const job = await prisma.discoveryJob.findUnique({
    where: { id: jobId },
    include: { engagement: { include: { members: true } } },
  });

  if (!job) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const isMember = job.engagement.members.some((m) => m.userId === session.user!.id);
  if (!isMember) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Topology summary — parsed from stored AzureTopology JSON (COMPLETED jobs only)
  let topologySummary: {
    vnets: number;
    subnets: number;
    firewalls: number;
    appGateways: number;
    dnsZones: number;
    expressRoutes: number;
  } | null = null;

  if (job.status === "COMPLETED" && job.topologyJson) {
    try {
      const topo = JSON.parse(job.topologyJson) as Record<string, unknown>;
      const subs = Array.isArray(topo.subscriptions)
        ? (topo.subscriptions as Record<string, unknown>[])
        : [];
      let vnets = 0, subnets = 0, firewalls = 0, appGateways = 0, dnsZones = 0, expressRoutes = 0;
      for (const sub of subs) {
        const subVnets = Array.isArray(sub.vnets)
          ? (sub.vnets as Record<string, unknown>[])
          : [];
        vnets += subVnets.length;
        for (const vnet of subVnets) {
          subnets += Array.isArray(vnet.subnets) ? (vnet.subnets as unknown[]).length : 0;
        }
        firewalls += Array.isArray(sub.firewalls) ? (sub.firewalls as unknown[]).length : 0;
        appGateways += Array.isArray(sub.app_gateways) ? (sub.app_gateways as unknown[]).length : 0;
        dnsZones += Array.isArray(sub.private_dns_zones) ? (sub.private_dns_zones as unknown[]).length : 0;
        expressRoutes += Array.isArray(sub.express_route_circuits) ? (sub.express_route_circuits as unknown[]).length : 0;
      }
      topologySummary = { vnets, subnets, firewalls, appGateways, dnsZones, expressRoutes };
    } catch {
      // ignore topology parse errors
    }
  }

  // Findings breakdown by severity (non-AI, COMPLETED jobs only)
  let findingsBySeverity: { severity: string; count: number }[] = [];
  if (job.status === "COMPLETED") {
    const groups = await prisma.finding.groupBy({
      by: ["severity"],
      where: { engagementId: job.engagementId, aiGenerated: false },
      _count: { id: true },
    });
    findingsBySeverity = groups.map((g) => ({ severity: g.severity, count: g._count.id }));
  }

  return NextResponse.json({
    id: job.id,
    status: job.status,
    startedAt: job.startedAt,
    completedAt: job.completedAt,
    findingsCount: job.findingsCount,
    errorMessage: job.errorMessage,
    progressLog: job.progressLog,
    updatedAt: job.updatedAt,
    topologySummary,
    findingsBySeverity,
  });
}
