"use client";

import { useActionState } from "react";
import { runAnalysis } from "../analysis/actions";
import { SubmitButton } from "@/components/ui/submit-button";

const ANALYSIS_OPTIONS = [
  {
    group: "Security Frameworks",
    items: [
      {
        value: "general",
        label: "General Security Review",
        desc: "Broad security posture across all categories — perimeter, segmentation, encryption, monitoring.",
      },
      {
        value: "zero_trust",
        label: "Zero Trust Assessment",
        desc: "Implicit trust zones, lateral movement risks, micro-segmentation gaps, identity-based network access.",
      },
      {
        value: "compliance_nist",
        label: "NIST SP 800-53",
        desc: "Map findings to NIST controls: SC-7 Boundary Protection, AC-4 Information Flow, SI-3 Malware.",
      },
      {
        value: "compliance_cis",
        label: "CIS Azure Benchmark",
        desc: "Evaluate against CIS Azure Foundations Benchmark v2.0 and CIS Controls v8.",
      },
      {
        value: "well_architected",
        label: "Azure Well-Architected",
        desc: "Security pillar review — defense in depth, least privilege, network segmentation best practices.",
      },
      {
        value: "remediation_priority",
        label: "Quick Wins",
        desc: "Surface highest-impact findings by exploitability × blast radius × remediation effort.",
      },
    ],
  },
  {
    group: "Network Behavioral Views",
    items: [
      {
        value: "traffic_flow",
        label: "Traffic Flow Analysis",
        desc: "East-west flows, north-south egress paths, bypassed inspection, unencrypted protocols, asymmetric inspection.",
      },
      {
        value: "dependency_chains",
        label: "Dependency Chains",
        desc: "Single points of failure, circular routing, shared service dependencies (DNS, NTP, AD), redundancy gaps.",
      },
      {
        value: "interconnect",
        label: "Interconnect Behavior",
        desc: "VNet peering configs, VPN/ER connectivity, vWAN hub routing, cross-tenant risks, route leaking.",
      },
      {
        value: "routing_decisions",
        label: "Routing Decisions",
        desc: "UDR overrides, BGP route scope, next-hop safety (NVA vs. Firewall vs. Internet), black-holes, prefix leaks.",
      },
      {
        value: "resilience",
        label: "Resilience Assumptions",
        desc: "Zone redundancy, active/active HA, health probe coverage, DDoS protection, SLA-breaking single points of failure.",
      },
    ],
  },
];

export function AiAnalysisForm({ engagementId }: { engagementId: string }) {
  const [state, action] = useActionState(runAnalysis, null);

  return (
    <form action={action} className="space-y-5">
      <input type="hidden" name="engagementId" value={engagementId} />

      {state?.error && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {state.error}
        </p>
      )}
      {state?.success && (
        <p className="rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-700 dark:border-teal-800 dark:bg-teal-900/20 dark:text-teal-300">
          Analysis complete — <strong>{state.count}</strong> new finding
          {state.count !== 1 ? "s" : ""} generated.
        </p>
      )}

      <div className="space-y-4">
        {ANALYSIS_OPTIONS.map((group) => (
          <div key={group.group}>
            <p className="label-caps mb-2 text-navy-300 dark:text-navy-500">
              {group.group}
            </p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {group.items.map((opt, i) => (
                <label
                  key={opt.value}
                  className="flex cursor-pointer items-start gap-3 rounded-xl border border-navy-100 bg-white/40 p-3 transition-colors hover:border-teal-400/60 hover:bg-teal-50/40 has-[:checked]:border-teal-500 has-[:checked]:bg-teal-50/60 dark:border-navy-700 dark:bg-navy-800/30 dark:hover:border-teal-600/60 dark:hover:bg-teal-900/20 dark:has-[:checked]:border-teal-500 dark:has-[:checked]:bg-teal-900/30"
                >
                  <input
                    type="radio"
                    name="focus"
                    value={opt.value}
                    defaultChecked={i === 0 && group.group === "Security Frameworks"}
                    className="mt-0.5 accent-teal-600"
                  />
                  <div>
                    <p className="text-xs font-semibold text-navy-700 dark:text-navy-100">
                      {opt.label}
                    </p>
                    <p className="mt-0.5 text-xs text-navy-400 dark:text-navy-400">
                      {opt.desc}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-navy-400 dark:text-navy-500">
        Analysis uses live topology data, uploaded documents, and existing findings as context.
        Run multiple types to build a comprehensive picture — duplicate findings are not re-created.
      </p>

      <div className="flex justify-end">
        <SubmitButton loadingText="Analyzing…">Run AI analysis</SubmitButton>
      </div>
    </form>
  );
}
