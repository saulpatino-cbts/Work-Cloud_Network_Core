"use client";

import { useActionState, useState } from "react";
import { runComplianceCheck } from "./actions";

const FRAMEWORKS = [
  { value: "nist", label: "NIST SP 800-53 Rev 5", desc: "Federal security controls for US government and critical infrastructure" },
  { value: "cis", label: "CIS Azure Foundations Benchmark v2.0", desc: "Prescriptive security configuration guidance for Azure" },
  { value: "soc2", label: "SOC 2 Type II (Trust Services Criteria)", desc: "Security, availability, and confidentiality for service organizations" },
  { value: "hipaa", label: "HIPAA Security Rule", desc: "Healthcare data security controls for ePHI protection" },
  { value: "pci", label: "PCI-DSS v4.0", desc: "Payment card industry data security standards" },
  { value: "waf", label: "Azure Well-Architected Framework (Security)", desc: "Microsoft security pillar best practices for Azure workloads" },
] as const;

type Framework = (typeof FRAMEWORKS)[number]["value"];

interface Props {
  engagementId: string;
  hasTopology: boolean;
}

export function ComplianceReportPanel({ engagementId, hasTopology }: Props) {
  const [framework, setFramework] = useState<Framework>("nist");
  const [state, action, isPending] = useActionState(runComplianceCheck, null);

  return (
    <section className="glass p-6">
      <h2 className="mb-1 text-lg font-semibold text-navy-100">Compliance Check</h2>
      <p className="mb-5 text-sm text-navy-400">
        Run a framework-specific compliance gap analysis against your discovered network
        topology. Results are saved as findings with framework control mappings.
      </p>

      {!hasTopology && (
        <p className="mb-4 rounded-lg border border-amber-800/40 bg-amber-900/20 px-4 py-3 text-sm text-amber-400">
          No discovery data yet. Run discovery on the Connections tab first.
        </p>
      )}

      <form action={action} className="space-y-4">
        <input type="hidden" name="engagementId" value={engagementId} />

        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-navy-400">
            Compliance Framework
          </label>
          <div className="grid gap-2 sm:grid-cols-2">
            {FRAMEWORKS.map((fw) => (
              <label
                key={fw.value}
                className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${
                  framework === fw.value
                    ? "border-teal-600/60 bg-teal-900/20"
                    : "border-navy-700/40 bg-navy-800/20 hover:border-navy-600/60"
                }`}
              >
                <input
                  type="radio"
                  name="framework"
                  value={fw.value}
                  checked={framework === fw.value}
                  onChange={() => setFramework(fw.value)}
                  className="mt-0.5 accent-teal-500"
                />
                <div>
                  <p className="text-xs font-semibold text-navy-100">{fw.label}</p>
                  <p className="mt-0.5 text-xs text-navy-400">{fw.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {state?.error && (
          <p className="rounded-lg border border-red-800/40 bg-red-900/20 px-4 py-2 text-sm text-red-400">
            {state.error}
          </p>
        )}
        {state?.success && (
          <p className="rounded-lg border border-teal-800/40 bg-teal-900/20 px-4 py-2 text-sm text-teal-300">
            ✓ Compliance check complete — {state.count} finding{state.count !== 1 ? "s" : ""} added with framework control mappings. View them on the Findings tab.
          </p>
        )}

        <button
          type="submit"
          disabled={isPending || !hasTopology}
          className="inline-flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isPending ? (
            <>
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Running compliance check…
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Run compliance check
            </>
          )}
        </button>
      </form>
    </section>
  );
}
