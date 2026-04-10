"use client";

import { useActionState } from "react";
import { generateDeliverable } from "./actions";
import { SubmitButton } from "@/components/ui/submit-button";

const DELIVERABLE_TYPES = [
  { value: "EXECUTIVE_SUMMARY", label: "Executive Summary" },
  { value: "TECHNICAL_FINDINGS", label: "Technical Findings Report" },
  { value: "REMEDIATION_PLAN", label: "Remediation Plan" },
  { value: "SPECIALIZATION_REPORT", label: "Specialization Report" },
];

export function GenerateDeliverableForm({
  engagementId,
}: {
  engagementId: string;
}) {
  const [state, action] = useActionState(generateDeliverable, null);

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
          Deliverable generated successfully.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="delType"
            className="block text-sm font-medium text-gray-700"
          >
            Deliverable type
          </label>
          <select
            id="delType"
            name="type"
            required
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {DELIVERABLE_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="delTitle"
            className="block text-sm font-medium text-gray-700"
          >
            Title
          </label>
          <input
            id="delTitle"
            name="title"
            type="text"
            required
            placeholder="e.g. ACME Corp — Technical Findings Q2 2026"
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="flex justify-end">
        <SubmitButton loadingText="Generating…">
          Generate deliverable
        </SubmitButton>
      </div>
    </form>
  );
}
