"use client";

import { useActionState } from "react";
import { deleteEngagement } from "@/app/(dashboard)/dashboard/actions";

interface Props {
  engagementId: string;
  engagementName: string;
  /** Visual style: "inline" for list rows, "header" for the engagement detail header */
  variant?: "inline" | "header";
}

export function DeleteEngagementButton({
  engagementId,
  engagementName,
  variant = "header",
}: Props) {
  const [_, formAction, isPending] = useActionState(
    async (prevState: any, formData: FormData) => {
      await deleteEngagement(formData);
      return prevState;
    },
    null
  );

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    if (
      !confirm(
        `Delete "${engagementName}"? This will permanently remove all documents, findings, and deliverables. This cannot be undone.`,
      )
    ) {
      e.preventDefault();
    }
  }

  if (variant === "inline") {
    return (
      <form
        action={formAction}
        onSubmit={handleSubmit}
        className="inline-block"
        onClick={(e) => e.stopPropagation()} // prevent Link navigation click bubbling
      >
        <input type="hidden" name="engagementId" value={engagementId} />
        <button
          type="submit"
          disabled={isPending}
          className="rounded border border-red-200 px-2 py-1 text-xs font-medium text-red-500 hover:bg-red-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-1"
        >
          {isPending ? "Deleting…" : "Delete"}
        </button>
      </form>
    );
  }

  return (
    <form action={formAction} onSubmit={handleSubmit} className="inline-block">
      <input type="hidden" name="engagementId" value={engagementId} />
      <button
        type="submit"
        disabled={isPending}
        className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-1"
      >
        {isPending ? "Deleting…" : "Delete engagement"}
      </button>
    </form>
  );
}
