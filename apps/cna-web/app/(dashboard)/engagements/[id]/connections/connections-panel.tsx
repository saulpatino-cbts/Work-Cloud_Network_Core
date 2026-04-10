"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { startDiscovery } from "../discovery/actions";
import { StatusBadge } from "@/components/ui/status-badge";
import { SubmitButton } from "@/components/ui/submit-button";
import type { CloudCredential, DiscoveryJob } from "@prisma/client";

type JobSummary = Pick<
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
const POLL_INTERVAL_MS = 3000;

// ─── Job log row ──────────────────────────────────────────────────────────────

function JobLogRow({ initial }: { initial: JobSummary }) {
  const [job, setJob] = useState(initial);
  const [expanded, setExpanded] = useState(ACTIVE_STATUSES.has(initial.status));
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(job.status)) return;
    function poll() {
      fetch(`/api/discovery-jobs/${job.id}`)
        .then((r) => r.json())
        .then((data: JobSummary) => {
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

  const progress: string[] = (() => {
    if (!job.progressLog) return [];
    try {
      return JSON.parse(job.progressLog) as string[];
    } catch {
      return [job.progressLog];
    }
  })();

  const isActive = ACTIVE_STATUSES.has(job.status);
  const isCompleted = job.status === "COMPLETED";
  const isFailed = job.status === "FAILED";

  return (
    <li className="rounded-lg border border-gray-100 bg-gray-50 p-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          {isCompleted ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
              <span>●</span> Discovery Completed
            </span>
          ) : (
            <StatusBadge value={job.status} variant="job" />
          )}
          {isActive && (
            <svg
              className="h-3.5 w-3.5 animate-spin text-blue-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isCompleted && job.findingsCount != null && (
            <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
              {job.findingsCount} finding{job.findingsCount !== 1 ? "s" : ""}
            </span>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            {expanded ? "Hide log ▲" : "Show log ▼"}
          </button>
        </div>
      </div>

      {/* Timestamps */}
      <p className="mt-1.5 text-xs text-gray-400">
        {job.startedAt
          ? `Started ${new Date(job.startedAt).toLocaleString()}`
          : "Queued"}
        {job.completedAt &&
          ` · Completed ${new Date(job.completedAt).toLocaleString()}`}
      </p>

      {/* Error */}
      {isFailed && job.errorMessage && (
        <div className="mt-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs font-mono text-red-700">
          {job.errorMessage}
        </div>
      )}

      {/* Progress log */}
      {expanded && progress.length > 0 && (
        <div className="mt-3 max-h-48 overflow-y-auto rounded border border-gray-200 bg-white p-3 font-mono text-xs text-gray-600">
          {progress.map((line, i) => (
            <div key={i} className={i === progress.length - 1 && isActive ? "font-semibold text-blue-600" : ""}>
              {line}
            </div>
          ))}
        </div>
      )}
    </li>
  );
}

// ─── Start Discovery form ─────────────────────────────────────────────────────

function StartDiscoveryForm({
  engagementId,
  credentialId,
}: {
  engagementId: string;
  credentialId: string;
}) {
  const [state, action] = useActionState(startDiscovery, null);
  return (
    <form action={action} className="inline-flex items-center gap-2">
      <input type="hidden" name="engagementId" value={engagementId} />
      <input type="hidden" name="credentialId" value={credentialId} />
      {state?.error && (
        <span className="text-xs text-red-600">{state.error}</span>
      )}
      <SubmitButton loadingText="Starting…">Start discovery</SubmitButton>
    </form>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface ConnectionsPanelProps {
  engagementId: string;
  credentials: Pick<CloudCredential, "id" | "label" | "platform" | "tenantId" | "subscriptionIds">[];
  jobs: JobSummary[];
}

export function ConnectionsPanel({
  engagementId,
  credentials,
  jobs,
}: ConnectionsPanelProps) {
  const latestJobByCredential = new Map<string, JobSummary>();
  for (const job of jobs) {
    if (!latestJobByCredential.has(job.credentialId)) {
      latestJobByCredential.set(job.credentialId, job);
    }
  }

  return (
    <div className="space-y-4">
      {credentials.length === 0 ? (
        <p className="text-sm text-gray-400">
          No connections yet. Add one in the section below.
        </p>
      ) : (
        <ul className="space-y-3">
          {credentials.map((cred) => {
            const lastJob = latestJobByCredential.get(cred.id);
            return (
              <li
                key={cred.id}
                className="flex items-start justify-between gap-4 rounded-lg border border-gray-200 p-4"
              >
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {cred.label}
                  </p>
                  <p className="text-xs text-gray-400">
                    {cred.platform} · Tenant: {cred.tenantId?.slice(0, 8)}…
                    {cred.subscriptionIds.length > 0
                      ? ` · ${cred.subscriptionIds.length} subscription(s)`
                      : " · All subscriptions"}
                  </p>
                  {lastJob && (
                    <p className="mt-1 text-xs text-gray-400">
                      Last run:{" "}
                      {lastJob.status === "COMPLETED"
                        ? `Completed ${new Date(lastJob.completedAt!).toLocaleDateString()}`
                        : lastJob.status}
                    </p>
                  )}
                </div>
                <StartDiscoveryForm
                  engagementId={engagementId}
                  credentialId={cred.id}
                />
              </li>
            );
          })}
        </ul>
      )}

      {/* Discovery history */}
      {jobs.length > 0 && (
        <div className="border-t border-gray-100 pt-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Discovery runs
          </p>
          <ul className="space-y-3">
            {jobs.map((job) => (
              <JobLogRow key={job.id} initial={job} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
