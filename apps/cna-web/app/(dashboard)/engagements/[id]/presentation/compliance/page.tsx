import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import {
  computeMaturityDimensions,
  getTopologyStats,
  SEV_COLORS,
  type Topology,
  type Finding,
  type MaturityDimension,
} from "../_lib/metrics";

interface PageProps {
  params: Promise<{ id: string }>;
}

// ── Maturity Radar SVG ─────────────────────────────────────────────────────────
function RadarChart({ dims }: { dims: MaturityDimension[] }) {
  const cx = 120, cy = 120, R = 88;
  const n = dims.length;
  const angleFor = (i: number) => (i * 2 * Math.PI) / n - Math.PI / 2;

  const gridPts = (level: number) =>
    dims
      .map((_, i) => {
        const rr = (level / 10) * R;
        return `${cx + rr * Math.cos(angleFor(i))},${cy + rr * Math.sin(angleFor(i))}`;
      })
      .join(" ");

  const dataPolygon = dims
    .map((d, i) => {
      const rr = (d.score / 10) * R;
      return `${cx + rr * Math.cos(angleFor(i))},${cy + rr * Math.sin(angleFor(i))}`;
    })
    .join(" ");

  const axes = dims.map((d, i) => ({
    ax: cx + R * Math.cos(angleFor(i)),
    ay: cy + R * Math.sin(angleFor(i)),
    lx: cx + (R + 28) * Math.cos(angleFor(i)),
    ly: cy + (R + 28) * Math.sin(angleFor(i)),
    sx: cx + ((d.score / 10) * R * 0.5 + R * 0.1) * Math.cos(angleFor(i)) + cx * 0,
    sy: cy + ((d.score / 10) * R * 0.5 + R * 0.1) * Math.sin(angleFor(i)) + cy * 0,
    label: d.label,
    score: d.score,
  }));

  return (
    <svg viewBox="0 0 240 240" className="h-56 w-56">
      {/* Grid rings */}
      {[2, 4, 6, 8, 10].map((level) => (
        <polygon
          key={level}
          points={gridPts(level)}
          fill="none"
          stroke="#1e2d3d"
          strokeWidth={level === 10 ? 1 : 0.5}
        />
      ))}
      {/* Axes */}
      {axes.map((ax, i) => (
        <line key={i} x1={cx} y1={cy} x2={ax.ax} y2={ax.ay} stroke="#1e2d3d" strokeWidth="0.75" />
      ))}
      {/* Data fill */}
      <polygon
        points={dataPolygon}
        fill="rgba(20,184,166,0.2)"
        stroke="#14b8a6"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {/* Score dots */}
      {dims.map((d, i) => {
        const rr = (d.score / 10) * R;
        return (
          <circle
            key={i}
            cx={cx + rr * Math.cos(angleFor(i))}
            cy={cy + rr * Math.sin(angleFor(i))}
            r="4"
            fill="#14b8a6"
          />
        );
      })}
      {/* Axis labels */}
      {axes.map((ax, i) => (
        <text
          key={i}
          x={ax.lx}
          y={ax.ly}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="8"
          fontWeight="600"
          fill="#94a3b8"
          fontFamily="sans-serif"
        >
          {ax.label}
        </text>
      ))}
      {/* Center label */}
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="9" fill="#64748b" fontFamily="sans-serif">
        Maturity
      </text>
    </svg>
  );
}

// ── Framework mapping ──────────────────────────────────────────────────────────
const FRAMEWORKS = [
  {
    name: "NIST CSF",
    description: "NIST Cybersecurity Framework",
    dims: [
      { dim: "Perimeter Defense",    func: "Protect"  },
      { dim: "Network Segmentation", func: "Protect"  },
      { dim: "Access Control",       func: "Protect"  },
      { dim: "Traffic Visibility",   func: "Detect"   },
      { dim: "Compliance Posture",   func: "Govern"   },
    ],
  },
  {
    name: "CIS Controls v8",
    description: "Center for Internet Security",
    dims: [
      { dim: "Perimeter Defense",    func: "CIS 12, 13"  },
      { dim: "Network Segmentation", func: "CIS 12"      },
      { dim: "Access Control",       func: "CIS 5, 6"    },
      { dim: "Traffic Visibility",   func: "CIS 8"       },
      { dim: "Compliance Posture",   func: "CIS 1, 2"    },
    ],
  },
  {
    name: "Azure CAF",
    description: "Cloud Adoption Framework Security",
    dims: [
      { dim: "Perimeter Defense",    func: "Network Security"    },
      { dim: "Network Segmentation", func: "Segmentation"        },
      { dim: "Access Control",       func: "Identity & Access"   },
      { dim: "Traffic Visibility",   func: "Logging & Monitoring"},
      { dim: "Compliance Posture",   func: "Policy & Governance" },
    ],
  },
];

function maturityLabel(score: number): { label: string; cls: string } {
  if (score >= 9) return { label: "Optimizing",   cls: "text-green-400 bg-green-900/20 border-green-800/40"   };
  if (score >= 7) return { label: "Managed",      cls: "text-teal-400 bg-teal-900/20 border-teal-800/40"       };
  if (score >= 5) return { label: "Defined",      cls: "text-amber-400 bg-amber-900/20 border-amber-800/40"   };
  if (score >= 3) return { label: "Developing",   cls: "text-orange-400 bg-orange-900/20 border-orange-800/40" };
  return               { label: "Initial",       cls: "text-red-400 bg-red-900/20 border-red-800/40"          };
}

export default async function CompliancePage({ params }: PageProps) {
  const { id } = await params;
  const session = await auth();

  const engagement = await prisma.engagement.findUnique({
    where: { id },
    include: {
      members: true,
      findings: { orderBy: [{ severity: "asc" }, { category: "asc" }] },
    },
  });
  if (!engagement) notFound();
  const isMember = engagement.members.some((m) => m.userId === session?.user?.id);
  if (!isMember) notFound();

  let topology: Topology | null = null;
  try {
    const job = await prisma.discoveryJob.findFirst({
      where: { engagementId: id, status: "COMPLETED" },
      orderBy: { completedAt: "desc" },
      select: { topologyJson: true },
    });
    if (job?.topologyJson) {
      try { topology = JSON.parse(job.topologyJson); } catch { /* ignore */ }
    }
  } catch { /* migration pending */ }

  const findings = engagement.findings as Finding[];
  const dims  = computeMaturityDimensions(topology, findings);
  const stats = getTopologyStats(topology);

  const avgScore = Math.round((dims.reduce((s, d) => s + d.score, 0) / dims.length) * 10) / 10;
  const overallLabel = maturityLabel(Math.round(avgScore));

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div>
        <p className="label-caps text-navy-500">Compliance & Maturity Assessment</p>
        <h1 className="mt-0.5 text-xl font-black text-navy-100">{engagement.clientOrg}</h1>
      </div>

      {/* ── Overall Score ── */}
      <div className="glass rounded-xl p-5">
        <div className="flex flex-col items-center gap-6 sm:flex-row">
          <RadarChart dims={dims} />
          <div className="flex-1 space-y-3">
            <div>
              <p className="label-caps text-navy-500">Overall Security Maturity</p>
              <p className="mt-1 text-4xl font-black text-navy-100">{avgScore}<span className="text-xl text-navy-400">/10</span></p>
              <span className={`mt-1 inline-block rounded-full border px-3 py-0.5 text-xs font-bold ${overallLabel.cls}`}>
                {overallLabel.label}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-navy-400">
              Maturity scored across five security dimensions based on discovered infrastructure
              and identified findings. Scores range from 1 (Initial) to 10 (Optimizing).
            </p>
            {topology && (
              <p className="text-xs text-navy-500">
                Assessment scope: {stats.subscriptions} subscription{stats.subscriptions !== 1 ? "s" : ""},{" "}
                {stats.vnets} VNet{stats.vnets !== 1 ? "s" : ""},{" "}
                {stats.subnets} subnet{stats.subnets !== 1 ? "s" : ""}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── Dimension Details ── */}
      <div className="glass rounded-xl p-6">
        <h2 className="mb-4 text-base font-bold text-navy-100">Dimension Breakdown</h2>
        <div className="space-y-4">
          {dims.map((d) => {
            const ml = maturityLabel(d.score);
            const complianceFindings = findings.filter(
              (f) =>
                f.severity !== "INFORMATIONAL" &&
                (f.category.toLowerCase().includes(d.fullLabel.toLowerCase().split(" ")[0].toLowerCase()) ||
                  d.fullLabel.toLowerCase().includes(f.category.toLowerCase())),
            );
            return (
              <div key={d.label} className="rounded-xl border border-navy-700/40 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-navy-100">{d.fullLabel}</p>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${ml.cls}`}>
                        {d.score}/10 · {ml.label}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-navy-400">{d.detail}</p>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="mt-3 overflow-hidden rounded-full bg-navy-800">
                  {/* eslint-disable-next-line react/forbid-dom-props */}
                  <div
                    className="h-2 rounded-full bg-teal-500 transition-all"
                    style={{ width: `${(d.score / 10) * 100}%` }}
                  />
                </div>
                {/* Contributing findings */}
                {complianceFindings.slice(0, 2).map((f, i) => {
                  const style = SEV_COLORS[f.severity as keyof typeof SEV_COLORS];
                  return (
                    <div key={i} className={`mt-2 flex items-center gap-2 rounded-lg border px-3 py-1.5 ${style.bg}`}>
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${style.bar}`} />
                      <p className="text-xs text-navy-300">{f.title}</p>
                      <span className={`ml-auto shrink-0 text-xs font-semibold ${style.text}`}>
                        {f.severity[0] + f.severity.slice(1).toLowerCase()}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Maturity Scale Reference ── */}
      <div className="glass rounded-xl p-6">
        <h2 className="mb-4 text-base font-bold text-navy-100">Maturity Scale</h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
          {[
            { range: "1–2", label: "Initial",     desc: "Ad-hoc, unpredictable processes", cls: "text-red-400 border-red-800/40 bg-red-900/10"       },
            { range: "3–4", label: "Developing",  desc: "Partial implementation, inconsistent", cls: "text-orange-400 border-orange-800/40 bg-orange-900/10" },
            { range: "5–6", label: "Defined",     desc: "Documented and consistently applied", cls: "text-amber-400 border-amber-800/40 bg-amber-900/10"   },
            { range: "7–8", label: "Managed",     desc: "Measured, quantitatively controlled", cls: "text-teal-400 border-teal-800/40 bg-teal-900/10"       },
            { range: "9–10",label: "Optimizing",  desc: "Continuous improvement focus", cls: "text-green-400 border-green-800/40 bg-green-900/10"      },
          ].map((level) => (
            <div key={level.label} className={`rounded-xl border p-3 text-center ${level.cls}`}>
              <p className="text-lg font-black">{level.range}</p>
              <p className="mt-0.5 text-xs font-bold">{level.label}</p>
              <p className="mt-1 text-xs opacity-80">{level.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Framework Mapping ── */}
      <div className="glass rounded-xl p-6">
        <h2 className="mb-4 text-base font-bold text-navy-100">Framework Alignment</h2>
        <p className="mb-4 text-xs text-navy-400">
          Maturity dimensions map to the following industry frameworks and controls.
        </p>
        <div className="space-y-5">
          {FRAMEWORKS.map((fw) => (
            <div key={fw.name}>
              <div className="mb-2 flex items-center gap-2">
                <p className="text-sm font-semibold text-navy-100">{fw.name}</p>
                <span className="text-xs text-navy-500">— {fw.description}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b border-navy-700/40">
                      <th className="pb-2 text-left font-medium text-navy-500">Dimension</th>
                      <th className="pb-2 text-left font-medium text-navy-500">Maps to</th>
                      <th className="pb-2 text-center font-medium text-navy-500">Score</th>
                      <th className="pb-2 text-left font-medium text-navy-500">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-700/30">
                    {fw.dims.map((row) => {
                      const dim = dims.find((d) => d.fullLabel === row.dim);
                      const score = dim?.score ?? 0;
                      const ml = maturityLabel(score);
                      return (
                        <tr key={row.dim}>
                          <td className="py-2 pr-4 font-medium text-navy-200">{row.dim}</td>
                          <td className="py-2 pr-4 text-navy-400">{row.func}</td>
                          <td className="py-2 text-center font-bold text-teal-400">{score}/10</td>
                          <td className="py-2">
                            <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${ml.cls}`}>
                              {ml.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
