"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { startDiscovery } from "./actions";
import { StatusBadge } from "@/components/ui/status-badge";
import { SubmitButton } from "@/components/ui/submit-button";
import type { CloudCredential, DiscoveryJob } from "@prisma/client";

type JobWithStatus = Pick<
  DiscoveryJob,
  | "id"
  | "status"
  | "startedAt"
  | "completedAt"
  | "findingsCount"
  | "errorMessage"
  | "progressLog"
  | "credentialId"
>;

const ACTIVE_STATUSES = new Set(["QUEUED", "RUNNING"]);
const POLL_INTERVAL_MS = 4000;

// ─── Single job row with live polling ────────────────────────────────────────

function JobRow({ initial }: { initial: JobWithStatus }) {
  const [job, setJob] = useState(initial);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(job.status)) return;

    function poll() {
      fetch(`/api/discovery-jobs/${job.id}`)
        .then((r) => r.json())
        .then((data: JobWithStatus) => {
          setJob(data);
          if (ACTIVE_STATUSES.has(data.status)) {
            timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
          }
        })
        .catch(() => {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS * 2);
        });
    }

    timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.id, job.status]);

  const progress: string[] = job.progressLog
    ? (() => {
        try {
          return JSON.parse(job.progressLog) as string[];
        } catch {
          return [job.progressLog];
        }
      })()
    : [];

  return (
    <li className="py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StatusBadge value={job.status} variant="job" />
            {ACTIVE_STATUSES.has(job.status) && (
              <svg
                className="h-3.5 w-3.5 animate-spin text-blue-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-400">
            {job.startedAt
              ? `Started ${new Date(job.startedAt).toLocaleString()}`
              : `Queued ${new Date().toLocaleString()}`}
            {job.completedAt &&
              ` · Completed ${new Date(job.completedAt).toLocaleString()}`}
            {job.findingsCount != null && ` · ${job.findingsCount} findings generated`}
          </p>
          {job.errorMessage && (
            <p className="mt-1 text-xs text-red-600">{job.errorMessage}</p>
          )}
          {progress.length > 0 && ACTIVE_STATUSES.has(job.status) && (
            <p className="mt-1 text-xs text-gray-500 italic">
              {progress[progress.length - 1]}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

// ─── Start Discovery form ─────────────────────────────────────────────────────

function StartDiscoveryForm({
  engagementId,
  credentialId,
  label,
}: {
  engagementId: string;
  credentialId: string;
  label: string;
}) {
  const [state, action] = useActionState(startDiscovery, null);

  return (
    <form action={action} className="inline-flex items-center">
      <input type="hidden" name="engagementId" value={engagementId} />
      <input type="hidden" name="credentialId" value={credentialId} />
      {state?.error && (
        <span className="mr-3 text-xs text-red-600">{state.error}</span>
      )}
      <SubmitButton loadingText="Starting…">
        Start discovery
      </SubmitButton>
    </form>
  );
}

// ─── Discovery panel ──────────────────────────────────────────────────────────

interface DiscoveryPanelProps {
  engagementId: string;
  credentials: Pick<CloudCredential, "id" | "label" | "platform" | "tenantId" | "subscriptionIds">[];
  jobs: JobWithStatus[];
}

export function DiscoveryPanel({
  engagementId,
  credentials,
  jobs,
}: DiscoveryPanelProps) {
  return (
    <div className="space-y-5">
      {/* Credential list with Start Discovery buttons */}
      {credentials.length > 0 ? (
        <ul className="divide-y divide-gray-100">
          {credentials.map((cred) => (
            <li key={cred.id} className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium text-gray-900">{cred.label}</p>
                <p className="text-xs text-gray-400">
                  {cred.platform} · Tenant: {cred.tenantId?.slice(0, 8)}…
                  {cred.subscriptionIds.length > 0
                    ? ` · ${cred.subscriptionIds.length} subscription(s) scoped`
                    : " · All subscriptions"}
                </p>
              </div>
              <StartDiscoveryForm
                engagementId={engagementId}
                credentialId={cred.id}
                label={cred.label}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-400">
          No cloud connections yet. Add one below.
        </p>
      )}

      {/* Jobs history */}
      {jobs.length > 0 && (
        <div className="border-t border-gray-100 pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
            Discovery runs
          </p>
          <ul className="divide-y divide-gray-100">
            {jobs.map((job) => (
              <JobRow key={job.id} initial={job} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
