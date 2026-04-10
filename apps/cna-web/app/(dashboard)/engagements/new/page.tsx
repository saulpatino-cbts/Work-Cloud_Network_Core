import { createEngagement } from "@/app/(dashboard)/dashboard/actions";
import { SubmitButton } from "@/components/ui/submit-button";
import Link from "next/link";

export default function NewEngagementPage() {
  return (
    <div className="mx-auto max-w-lg">
      <div className="mb-6">
        <Link
          href="/dashboard"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← Back to dashboard
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-gray-900">
          New Engagement
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Start a Cloud Network Assessment for a client organization.
        </p>
      </div>

      <form
        action={createEngagement}
        className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-5"
      >
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-gray-700"
          >
            Engagement name
          </label>
          <input
            id="name"
            name="name"
            type="text"
            required
            placeholder="e.g. ACME Corp — Q2 2026 Network Assessment"
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label
            htmlFor="clientOrg"
            className="block text-sm font-medium text-gray-700"
          >
            Client organization
          </label>
          <input
            id="clientOrg"
            name="clientOrg"
            type="text"
            required
            placeholder="e.g. ACME Corp"
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <Link
            href="/dashboard"
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Cancel
          </Link>
          <SubmitButton loadingText="Creating…">Create engagement</SubmitButton>
        </div>
      </form>
    </div>
  );
}
