"use client";

import { useActionState } from "react";
import { runAnalysis } from "./actions";
import { SubmitButton } from "@/components/ui/submit-button";

export function RunAnalysisForm({ engagementId }: { engagementId: string }) {
  const [state, action] = useActionState(runAnalysis, null);

  return (
    <form action={action} className="space-y-3">
      <input type="hidden" name="engagementId" value={engagementId} />

      {state?.error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {state.error}
        </p>
      )}
      {state?.success && (
        <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
          Analysis complete — {state.count} finding
          {state.count !== 1 ? "s" : ""} generated.
        </p>
      )}

      <SubmitButton loadingText="Analyzing…">Run AI analysis</SubmitButton>
    </form>
  );
}
