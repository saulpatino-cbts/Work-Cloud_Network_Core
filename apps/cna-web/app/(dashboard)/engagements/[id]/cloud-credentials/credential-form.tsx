"use client";

import { useState, useTransition, useRef } from "react";
import { addBulkCredentials, testAzureConnection } from "./actions";

type Platform = "AZURE" | "AWS";

interface Subscription {
  name: string;
  subscriptionId: string;
  tenantId?: string; // per-row override from CSV
}

const GUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isGuid = (s: string) => GUID_RE.test(s.trim());

function parseSubscriptionCsv(text: string): {
  subs: Subscription[];
  errors: string[];
} {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length) return { subs: [], errors: ["CSV file is empty."] };

  // Skip header row if it contains the word "subscription"
  const dataLines = lines[0].toLowerCase().includes("subscription")
    ? lines.slice(1)
    : lines;

  const errors: string[] = [];
  const subs: Subscription[] = [];

  for (let i = 0; i < dataLines.length; i++) {
    const cols = dataLines[i]
      .split(",")
      .map((c) => c.trim().replace(/^"|"$/g, ""));
    const [rawName = "", rawSubId = "", rawTenantId = ""] = cols;

    if (!rawName && !rawSubId) continue;

    if (!isGuid(rawSubId)) {
      errors.push(`Row ${i + 1}: "${rawSubId}" is not a valid subscription ID (expected GUID)`);
      continue;
    }
    if (rawTenantId && !isGuid(rawTenantId)) {
      errors.push(`Row ${i + 1}: "${rawTenantId}" is not a valid tenant ID (expected GUID)`);
      continue;
    }

    subs.push({
      name: rawName.trim() || rawSubId.trim(),
      subscriptionId: rawSubId.trim(),
      tenantId: rawTenantId.trim() || undefined,
    });
  }

  return { subs, errors };
}

function downloadTemplate() {
  const csv = [
    "subscription_name,subscription_id,tenant_id",
    "Production,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "Staging,yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "subscription_import_template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function CredentialForm({ engagementId }: { engagementId: string }) {
  const [platform, setPlatform] = useState<Platform>("AZURE");

  // Auth fields
  const [tenantId, setTenantId] = useState("");
  const [spClientId, setSpClientId] = useState("");
  const [spClientSecret, setSpClientSecret] = useState("");

  // Subscription list (pending — not yet saved)
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [manualName, setManualName] = useState("");
  const [manualSubId, setManualSubId] = useState("");
  const [manualSubIdError, setManualSubIdError] = useState("");
  const [csvErrors, setCsvErrors] = useState<string[]>([]);

  // Results
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    subscriptions?: string[];
    error?: string;
  } | null>(null);
  const [saveResult, setSaveResult] = useState<{
    error?: string;
    success?: boolean;
    count?: number;
  } | null>(null);

  const [isTesting, startTest] = useTransition();
  const [isSaving, startSave] = useTransition();
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleCsvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      const { subs, errors } = parseSubscriptionCsv(text);
      setCsvErrors(errors);
      setSaveResult(null);

      if (subs.length > 0) {
        // Auto-fill tenant ID from first row if the field is blank
        if (!tenantId && subs[0].tenantId) setTenantId(subs[0].tenantId);

        setSubscriptions((prev) => {
          const existing = new Set(prev.map((s) => s.subscriptionId));
          const newOnes = subs.filter((s) => !existing.has(s.subscriptionId));
          return [...prev, ...newOnes];
        });
      }
    };
    reader.readAsText(file);
    // Reset so the same file can be re-uploaded after edits
    e.target.value = "";
  }

  function addManual() {
    const subId = manualSubId.trim();
    if (!subId) return;
    if (!isGuid(subId)) {
      setManualSubIdError("Must be a GUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)");
      return;
    }
    if (subscriptions.some((s) => s.subscriptionId === subId)) {
      setManualSubIdError("This subscription ID is already in the list.");
      return;
    }
    setManualSubIdError("");
    setSubscriptions((prev) => [
      ...prev,
      { name: manualName.trim() || subId, subscriptionId: subId },
    ]);
    setManualName("");
    setManualSubId("");
    setSaveResult(null);
  }

  function removeSubscription(subscriptionId: string) {
    setSubscriptions((prev) => prev.filter((s) => s.subscriptionId !== subscriptionId));
    setSaveResult(null);
  }

  function handleTest() {
    setTestResult(null);
    startTest(async () => {
      const result = await testAzureConnection({ tenantId, spClientId, spClientSecret });
      setTestResult(result);
    });
  }

  function handleSave() {
    setSaveResult(null);
    startSave(async () => {
      const result = await addBulkCredentials({
        engagementId,
        tenantId,
        spClientId,
        spClientSecret,
        subscriptions,
      });
      setSaveResult(result);
      if (result.success) {
        setSubscriptions([]);
        setManualName("");
        setManualSubId("");
        setCsvErrors([]);
        setTestResult(null);
      }
    });
  }

  const canTest = !!tenantId && !!spClientId && !!spClientSecret;
  const canSave = canTest && subscriptions.length > 0 && !isSaving;

  return (
    <div className="space-y-5">
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
        <div className="space-y-6">
          {/* ── Authentication ── */}
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
              Authentication
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Tenant ID
                </label>
                <input
                  type="text"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  SP Client ID
                </label>
                <input
                  type="text"
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
                  type="password"
                  value={spClientSecret}
                  onChange={(e) => setSpClientSecret(e.target.value)}
                  placeholder="••••••••••••••••"
                  autoComplete="new-password"
                  className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* ── Subscriptions ── */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Subscriptions
                {subscriptions.length > 0 && (
                  <span className="ml-1.5 font-normal normal-case text-gray-400">
                    ({subscriptions.length} pending)
                  </span>
                )}
              </p>
              <div className="flex items-center gap-4 text-xs">
                <button
                  type="button"
                  onClick={downloadTemplate}
                  className="text-blue-600 hover:underline"
                >
                  Download template
                </button>
                <label className="cursor-pointer text-blue-600 hover:underline">
                  Import CSV
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,text/csv"
                    onChange={handleCsvUpload}
                    className="sr-only"
                  />
                </label>
              </div>
            </div>

            {/* CSV parse errors */}
            {csvErrors.length > 0 && (
              <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {csvErrors.map((err, i) => (
                  <p key={i}>{err}</p>
                ))}
              </div>
            )}

            {/* Chips */}
            {subscriptions.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {subscriptions.map((sub) => (
                  <span
                    key={sub.subscriptionId}
                    className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs text-blue-800"
                  >
                    <span className="font-medium">{sub.name}</span>
                    <span className="text-blue-400">
                      {sub.subscriptionId.slice(0, 8)}…
                    </span>
                    <button
                      type="button"
                      onClick={() => removeSubscription(sub.subscriptionId)}
                      className="ml-0.5 rounded-full p-0.5 text-blue-400 hover:bg-blue-200 hover:text-blue-700"
                      title={`Remove ${sub.name}`}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Manual add row */}
            <div className="flex gap-2">
              <input
                type="text"
                value={manualName}
                onChange={(e) => setManualName(e.target.value)}
                placeholder="Subscription name"
                className="w-48 shrink-0 rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <div className="flex flex-1 flex-col">
                <input
                  type="text"
                  value={manualSubId}
                  onChange={(e) => {
                    setManualSubId(e.target.value);
                    setManualSubIdError("");
                  }}
                  onKeyDown={(e) => e.key === "Enter" && addManual()}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className={`block w-full rounded-lg border px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-1 ${
                    manualSubIdError
                      ? "border-red-300 focus:border-red-400 focus:ring-red-300"
                      : "border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                  }`}
                />
                {manualSubIdError && (
                  <p className="mt-1 text-xs text-red-600">{manualSubIdError}</p>
                )}
              </div>
              <button
                type="button"
                onClick={addManual}
                disabled={!manualSubId.trim()}
                className="shrink-0 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Add
              </button>
            </div>
            <p className="mt-1.5 text-xs text-gray-400">
              Add subscriptions individually or import a CSV (subscription_name, subscription_id, tenant_id).
              Tenant ID from CSV auto-fills the field above if blank.
            </p>
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

          {/* Save result */}
          {saveResult && (
            <div
              className={`rounded-lg px-3 py-2 text-sm ${
                saveResult.success
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {saveResult.success
                ? `${saveResult.count} subscription${saveResult.count !== 1 ? "s" : ""} saved.`
                : saveResult.error}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={handleTest}
              disabled={isTesting || !canTest}
              className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isTesting ? "Testing…" : "Test connection"}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={!canSave}
              className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSaving
                ? "Saving…"
                : subscriptions.length > 1
                  ? `Save ${subscriptions.length} subscriptions`
                  : "Save connection"}
            </button>
          </div>
        </div>
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
