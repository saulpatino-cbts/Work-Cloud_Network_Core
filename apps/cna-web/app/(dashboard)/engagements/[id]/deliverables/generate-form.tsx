"use client";

import { useActionState, useRef } from "react";
import { generateDeliverable } from "./actions";
import { SubmitButton } from "@/components/ui/submit-button";

const DELIVERABLE_TYPES = [
  {
    value: "EXECUTIVE_SUMMARY",
    label: "Executive Summary",
    audience: "CxO / CISO / Board",
    desc: "Top 5 risks in business language, severity breakdown, 30/60/90-day recommendations.",
  },
  {
    value: "TECHNICAL_FINDINGS",
    label: "Technical Findings Report",
    audience: "Security Engineers / Architects",
    desc: "Every finding with detailed description, root cause, Azure CLI remediation steps, and MS Learn references.",
  },
  {
    value: "REMEDIATION_PLAN",
    label: "Remediation Plan",
    audience: "IT / Platform Team",
    desc: "Prioritized task list with numbered steps, validation checks, rollback procedures, and effort estimates.",
  },
  {
    value: "SPECIALIZATION_REPORT",
    label: "Specialization Report",
    audience: "Security Architect / Compliance",
    desc: "Framework gap analysis (NIST/CIS/WAF), maturity scoring, compliance gap register, architecture recommendations.",
  },
];

export function GenerateDeliverableForm({
  engagementId,
}: {
  engagementId: string;
}) {
  const [state, action] = useActionState(generateDeliverable, null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function clientAction(formData: FormData) {
    // Convert logo file to base64 data URL if provided
    const file = fileRef.current?.files?.[0];
    if (file) {
      const reader = new FileReader();
      const dataUrl = await new Promise<string>((resolve) => {
        reader.onload = () => resolve(reader.result as string);
        reader.readAsDataURL(file);
      });
      formData.set("customerLogoUrl", dataUrl);
    }
    return action(formData);
  }

  return (
    <form action={clientAction} className="space-y-5">
      <input type="hidden" name="engagementId" value={engagementId} />

      {state?.error && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {state.error}
        </p>
      )}
      {state?.success && (
        <p className="rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-700 dark:border-teal-800 dark:bg-teal-900/20 dark:text-teal-300">
          Deliverable generated successfully. Scroll up to view and publish it.
        </p>
      )}

      {/* Report type */}
      <div>
        <p className="label-caps mb-2 text-navy-300 dark:text-navy-500">Report Type</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {DELIVERABLE_TYPES.map((opt, i) => (
            <label
              key={opt.value}
              className="flex cursor-pointer items-start gap-3 rounded-xl border border-navy-100 bg-white/40 p-3.5 transition-colors hover:border-teal-400/60 hover:bg-teal-50/40 has-[:checked]:border-teal-500 has-[:checked]:bg-teal-50/60 dark:border-navy-700 dark:bg-navy-800/30 dark:hover:border-teal-600/60 dark:has-[:checked]:border-teal-500 dark:has-[:checked]:bg-teal-900/30"
            >
              <input
                type="radio"
                name="type"
                value={opt.value}
                defaultChecked={i === 0}
                className="mt-0.5 accent-teal-600"
              />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-navy-700 dark:text-navy-100">
                  {opt.label}
                </p>
                <p className="mt-0.5 text-xs text-navy-500 dark:text-navy-400">
                  <span className="font-medium text-teal-600 dark:text-teal-400">
                    {opt.audience}
                  </span>{" "}
                  · {opt.desc}
                </p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Title */}
      <div>
        <label
          htmlFor="delTitle"
          className="label-caps block text-navy-300 dark:text-navy-500"
        >
          Document Title
        </label>
        <input
          id="delTitle"
          name="title"
          type="text"
          required
          placeholder="e.g. ACME Corp — Cloud Network Assessment Q2 2026"
          className="mt-1.5 block w-full rounded-xl border border-navy-100 bg-white/60 px-3.5 py-2.5 text-sm text-navy-800 placeholder-navy-300 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-navy-700 dark:bg-navy-800/40 dark:text-navy-100 dark:placeholder-navy-600"
        />
      </div>

      {/* Customer logo */}
      <div>
        <p className="label-caps mb-1.5 text-navy-300 dark:text-navy-500">
          Customer Logo (optional)
        </p>
        <p className="mb-2 text-xs text-navy-400 dark:text-navy-500">
          Upload a PNG or SVG to personalize the report header. Leave blank to use the CBTS logo.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/svg+xml"
          aria-label="Customer logo image file (PNG or SVG)"
          className="block w-full text-sm text-navy-500 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-teal-700 hover:file:bg-teal-100 dark:text-navy-400 dark:file:bg-teal-900/30 dark:file:text-teal-300"
        />
      </div>

      <p className="text-xs text-navy-400 dark:text-navy-500">
        AI generation uses all available data: live topology, uploaded documents, and existing findings.
        Generation typically takes 20–60 seconds.
      </p>

      <div className="flex justify-end">
        <SubmitButton loadingText="Generating (this may take ~30s)…">
          Generate deliverable
        </SubmitButton>
      </div>
    </form>
  );
}
