"use client";

import { useActionState } from "react";
import { runAnalysis } from "../analysis/actions";
import { SubmitButton } from "@/components/ui/submit-button";

const ANALYSIS_OPTIONS = [
  {
    value: "general",
    label: "General Security Review",
    desc: "Broad security posture review across all categories.",
  },
  {
    value: "zero_trust",
    label: "Zero Trust Assessment",
    desc: "Identify implicit trust zones, lateral movement risks, and micro-segmentation gaps.",
  },
  {
    value: "compliance_nist",
    label: "NIST SP 800-53",
    desc: "Map findings to NIST network security controls (SC-7, AC-4, SI-3).",
  },
  {
    value: "compliance_cis",
    label: "CIS Azure Benchmark",
    desc: "Evaluate against CIS Azure Foundations Benchmark and CIS Controls v8.",
  },
  {
    value: "well_architected",
    label: "Azure Well-Architected",
    desc: "Review against the Azure WAF Security pillar — defense in depth and least privilege.",
  },
  {
    value: "remediation_priority",
    label: "Quick Wins / Remediation Priority",
    desc: "Surface highest-impact findings that can be remediated quickly.",
  },
];

export function AiAnalysisForm({ engagementId }: { engagementId: string }) {
  const [state, action] = useActionState(runAnalysis, null);

  return (
    <form action={action} className="space-y-4">
      <input type="hidden" name="engagementId" value={engagementId} />

      {state?.error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {state.error}
        </p>
      )}
      {state?.success && (
        <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
          Analysis complete — {state.count} new finding
          {state.count !== 1 ? "s" : ""} generated.
        </p>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700">
          Analysis focus
        </label>
        <p className="mb-2 text-xs text-gray-400">
          Each type uses a different prompt — run multiple to build a complete
          picture. Duplicate findings are not re-created.
        </p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {ANALYSIS_OPTIONS.map((opt, i) => (
            <label
              key={opt.value}
              className="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-200 p-3 hover:border-blue-300 hover:bg-blue-50 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50"
            >
              <input
                type="radio"
                name="focus"
                value={opt.value}
                defaultChecked={i === 0}
                className="mt-0.5 accent-blue-600"
              />
              <div>
                <p className="text-xs font-semibold text-gray-800">
                  {opt.label}
                </p>
                <p className="text-xs text-gray-500">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="flex justify-end">
        <SubmitButton loadingText="Analyzing…">Run AI analysis</SubmitButton>
      </div>
    </form>
  );
}
