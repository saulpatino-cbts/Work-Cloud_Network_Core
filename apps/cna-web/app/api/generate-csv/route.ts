import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.id) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const engagementId = searchParams.get("engagementId");
  const template = searchParams.get("template");

  if (!engagementId || !template) {
    return new NextResponse("Missing engagementId or template", { status: 400 });
  }

  // Verify membership
  const member = await prisma.engagementMember.findUnique({
    where: { engagementId_userId: { engagementId, userId: session.user.id } },
  });
  if (!member) return new NextResponse("Forbidden", { status: 403 });

  // Get latest completed discovery job
  let topology: Record<string, unknown> | null = null;
  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { topologyJson: true },
    });
    if (job?.topologyJson) {
      topology = JSON.parse(job.topologyJson) as Record<string, unknown>;
    }
  } catch { /* ok */ }

  if (!topology) {
    return new NextResponse("No discovery data available", { status: 404 });
  }

  const subs = (topology.subscriptions as unknown[]) ?? [];
  let csv = "";
  let filename = template;

  if (template.includes("Subscription Inventory")) {
    const rows = ["subscription_id,subscription_name,tenant_id,management_group,state"];
    for (const sub of subs as Record<string, unknown>[]) {
      const id = String(sub.subscription_id ?? "");
      const name = String(sub.subscription_name ?? "");
      const tenantId = String(topology.tenant_id ?? "");
      rows.push(`${id},"${name}",${tenantId},,Enabled`);
    }
    csv = rows.join("\n");
    filename = "Azure Subscription Inventory.csv";

  } else if (template.includes("NSG Rule Export")) {
    const rows = ["nsg_name,resource_group,subnet,priority,direction,protocol,source,destination,destination_port,action"];
    for (const sub of subs as Record<string, unknown>[]) {
      for (const nsg of ((sub.nsgs ?? []) as Record<string, unknown>[])) {
        const nsgName = String(nsg.name ?? "");
        const rg = String(nsg.resource_group ?? "");
        const associatedSubnets = (nsg.associated_subnet_ids as string[] | undefined) ?? [];
        const subnetNames = associatedSubnets.map((s) => s.split("/").pop() ?? "").join("|");
        for (const rule of ((nsg.security_rules ?? []) as Record<string, unknown>[])) {
          const src = String((rule.source_address_prefix ?? rule.source_address_prefixes) ?? "*");
          const dst = String((rule.destination_address_prefix ?? rule.destination_address_prefixes) ?? "*");
          const port = String((rule.destination_port_range ?? rule.destination_port_ranges) ?? "*");
          rows.push(`"${nsgName}","${rg}","${subnetNames}",${rule.priority},${rule.direction},${rule.protocol},"${src}","${dst}","${port}",${rule.access}`);
        }
      }
    }
    csv = rows.join("\n");
    filename = "NSG Rule Export.csv";

  } else if (template.includes("Firewall Policy")) {
    const rows = ["rule_collection,priority,rule_name,source,destination,protocol,ports,action"];
    for (const sub of subs as Record<string, unknown>[]) {
      for (const fw of ((sub.firewalls ?? []) as Record<string, unknown>[])) {
        rows.push(`"${fw.name}",100,"Firewall discovered","*","*","Any","*",Allow`);
      }
    }
    if (rows.length === 1) rows.push("# No Azure Firewall instances found in this engagement");
    csv = rows.join("\n");
    filename = "Firewall Policy Rules.csv";

  } else if (template.includes("Route Table")) {
    const rows = ["route_table_name,resource_group,route_name,address_prefix,next_hop_type,next_hop_ip_address"];
    for (const sub of subs as Record<string, unknown>[]) {
      for (const rt of ((sub.route_tables ?? []) as Record<string, unknown>[])) {
        for (const route of ((rt.routes ?? []) as Record<string, unknown>[])) {
          rows.push(`"${rt.name}","${rt.resource_group}","${route.name}","${route.address_prefix}","${route.next_hop_type}","${route.next_hop_ip ?? ""}"`);
        }
      }
    }
    csv = rows.join("\n");
    filename = "Route Table Export.csv";

  } else {
    return new NextResponse("Unknown template", { status: 400 });
  }

  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
