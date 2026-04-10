"use client";

import { useActionState, useState, useTransition } from "react";
import { addCloudCredential, testAzureConnection } from "./actions";
import { SubmitButton } from "@/components/ui/submit-button";

type Platform = "AZURE" | "AWS";

interface TestResult {
  ok: boolean;
  subscriptions?: string[];
  error?: string;
}

export function CredentialForm({ engagementId }: { engagementId: string }) {
  const [platform, setPlatform] = useState<Platform>("AZURE");
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [isTesting, startTest] = useTransition();

  // Form field state (controlled so we can read values for test-connection)
  const [label, setLabel] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [subscriptionIds, setSubscriptionIds] = useState("");
  const [spClientId, setSpClientId] = useState("");
  const [spClientSecret, setSpClientSecret] = useState("");

  const [saveState, saveAction] = useActionState(addCloudCredential, null);

  function handleTest() {
    setTestResult(null);
    startTest(async () => {
      const result = await testAzureConnection({ tenantId, spClientId, spClientSecret });
      setTestResult(result);
    });
  }

  return (
    <div className="space-y-4">
      {/* Platform tabs */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setPlatform("AZURE")}
          className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
            platform === "AZURE"
              ? "bg-blue-600 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          Azure
        </button>
        <button
          type="button"
          disabled
          title="AWS support coming soon"
          className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-4 py-1.5 text-sm font-medium text-gray-400 cursor-not-allowed"
        >
          AWS
          <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
            soon
          </span>
        </button>
      </div>

      {platform === "AZURE" && (
        <form action={saveAction} className="space-y-4">
          <input type="hidden" name="engagementId" value={engagementId} />

          {saveState?.error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {saveState.error}
            </p>
          )}
          {saveState?.success && (
            <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
              Connection saved.
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Label
              </label>
              <input
                name="label"
                type="text"
                required
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. ACME Corp Production"
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Tenant ID
              </label>
              <input
                name="tenantId"
                type="text"
                required
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700">
                Subscription IDs{" "}
                <span className="text-gray-400 font-normal">(optional — blank discovers all)</span>
              </label>
              <input
                name="subscriptionIds"
                type="text"
                value={subscriptionIds}
                onChange={(e) => setSubscriptionIds(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx, ..."
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-400">
                Comma-separated. Leave blank to discover all subscriptions accessible to this service principal.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                SP Client ID
              </label>
              <input
                name="spClientId"
                type="text"
                required
                value={spClientId}
                onChange={(e) => setSpClientId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                SP Client Secret
              </label>
              <input
                name="spClientSecret"
                type="password"
                required
                value={spClientSecret}
                onChange={(e) => setSpClientSecret(e.target.value)}
                placeholder="••••••••••••••••"
                autoComplete="new-password"
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Test connection result */}
          {testResult && (
            <div
              className={`rounded-lg px-3 py-2 text-sm ${
                testResult.ok
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {testResult.ok ? (
                <>
                  <p className="font-medium">Connection successful</p>
                  {testResult.subscriptions && testResult.subscriptions.length > 0 && (
                    <ul className="mt-1 list-disc pl-4 text-xs">
                      {testResult.subscriptions.slice(0, 10).map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                      {testResult.subscriptions.length > 10 && (
                        <li>+{testResult.subscriptions.length - 10} more</li>
                      )}
                    </ul>
                  )}
                </>
              ) : (
                <p>{testResult.error}</p>
              )}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={handleTest}
              disabled={isTesting || !tenantId || !spClientId || !spClientSecret}
              className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isTesting ? "Testing…" : "Test connection"}
            </button>
            <SubmitButton loadingText="Saving…">Save connection</SubmitButton>
          </div>
        </form>
      )}

      {platform === "AWS" && (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
          <p className="text-sm text-gray-500">AWS discovery is coming soon.</p>
          <p className="mt-1 text-xs text-gray-400">
            Switch to Azure to add a connection now.
          </p>
        </div>
      )}
    </div>
  );
}
