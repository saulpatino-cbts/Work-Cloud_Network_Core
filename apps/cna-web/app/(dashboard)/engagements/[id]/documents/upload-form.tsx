"use client";

import { useActionState } from "react";
import { uploadDocument } from "./actions";
import { SubmitButton } from "@/components/ui/submit-button";

const DOC_TYPE_OPTIONS = [
  { value: "CLIENT_ARCHITECTURE", label: "Client Architecture" },
  { value: "COMPLIANCE_FRAMEWORK", label: "Compliance Framework" },
  { value: "NETWORK_DIAGRAM", label: "Network Diagram" },
  { value: "CONFIGURATION_EXPORT", label: "Configuration Export" },
  { value: "OTHER", label: "Other" },
];

const ACCEPTED = ".csv,.txt,.json,.yaml,.yml,.pdf,.xlsx";

export function UploadDocumentForm({ engagementId }: { engagementId: string }) {
  const [state, action] = useActionState(uploadDocument, null);

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
          Document uploaded successfully.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="docType"
            className="block text-sm font-medium text-gray-700"
          >
            Document type
          </label>
          <select
            id="docType"
            name="docType"
            required
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {DOC_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="file"
            className="block text-sm font-medium text-gray-700"
          >
            File
          </label>
          <input
            id="file"
            name="file"
            type="file"
            required
            accept={ACCEPTED}
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1 file:text-xs file:font-medium file:text-blue-700 focus:outline-none"
          />
          <p className="mt-1 text-xs text-gray-400">
            CSV, TXT, JSON, YAML — text files are parsed for AI analysis. PDF,
            XLSX stored as-is.
          </p>
        </div>
      </div>

      <div className="flex justify-end">
        <SubmitButton loadingText="Uploading…">Upload document</SubmitButton>
      </div>
    </form>
  );
}
