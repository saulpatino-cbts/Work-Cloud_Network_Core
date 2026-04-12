"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { startDiscovery } from "../discovery/actions";
import { deleteCloudCredential } from "../cloud-credentials/actions";
import { StatusBadge } from "@/components/ui/status-badge";
import { SubmitButton } from "@/components/ui/submit-button";
import type { CloudCredential, DiscoveryJob } from "@prisma/client";

// ─── Types ────────────────────────────────────────────────────────────────────

type TopologySummary = {
  vnets: number;
  subnets: number;
  firewalls: number;
  appGateways: number;
  dnsZones: number;
  expressRoutes: number;
};

type SeverityCount = { severity: string; count: number };

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
> & {
  topologySummary?: TopologySummary | null;
  findingsBySeverity?: SeverityCount[];
};

const ACTIVE_STATUSES = new Set(["QUEUED", "RUNNING"]);
const POLL_INTERVAL_MS = 3000;

const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];
const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "bg-red-900/30 text-red-400",
  HIGH: "bg-orange-900/30 text-orange-400",
  MEDIUM: "bg-yellow-900/30 text-yellow-400",
  LOW: "bg-blue-900/30 text-blue-400",
  INFORMATIONAL: "bg-navy-700/40 text-navy-300",
};

// ─── Inline job entry (inside collapsible) ────────────────────────────────────

function JobEntry({
  initial,
  onUpdate,
}: {
  initial: JobSummary;
  onUpdate?: (job: JobSummary) => void;
}) {
  const [job, setJob] = useState(initial);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(job.status)) return;
    function poll() {
      fetch(`/api/discovery-jobs/${job.id}`)
        .then((r) => r.json())
        .then((data: JobSummary) => {
          setJob(data);
          onUpdate?.(data);
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

  const severityCounts = SEVERITY_ORDER.map((sev) => {
    const found = job.findingsBySeverity?.find((s) => s.severity === sev);
    return { severity: sev, count: found?.count ?? 0 };
  }).filter((s) => s.count > 0);

  return (
    <div className="rounded-lg border border-navy-700/40 bg-navy-800/30 p-3">
      {/* Status + timestamp */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isCompleted ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-teal-900/40 px-2 py-0.5 text-xs font-semibold text-teal-400">
              ● Completed
            </span>
          ) : (
            <StatusBadge value={job.status} variant="job" />
          )}
          {isActive && (
            <svg className="h-3.5 w-3.5 animate-spin text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isCompleted && job.findingsCount != null && (
            <span className="rounded-full bg-blue-900/30 px-2 py-0.5 text-xs font-semibold text-blue-400">
              {job.findingsCount} finding{job.findingsCount !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <p className="text-xs text-navy-400">
          {job.startedAt
            ? new Date(job.startedAt).toLocaleString()
            : "Queued"}
          {job.completedAt && ` → ${new Date(job.completedAt).toLocaleString()}`}
        </p>
      </div>

      {/* Error */}
      {isFailed && job.errorMessage && (
        <div className="mt-2 rounded border border-red-800/40 bg-red-900/20 px-3 py-2 text-xs font-mono text-red-400">
          {job.errorMessage}
        </div>
      )}

      {/* Severity counts */}
      {isCompleted && severityCounts.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {severityCounts.map(({ severity, count }) => (
            <span
              key={severity}
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLE[severity] ?? "bg-navy-700/40 text-navy-300"}`}
            >
              {severity}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Topology summary */}
      {isCompleted && job.topologySummary && (
        <div className="mt-2 flex flex-wrap gap-2">
          {[
            { label: "VNets", value: job.topologySummary.vnets },
            { label: "Subnets", value: job.topologySummary.subnets },
            { label: "Firewalls", value: job.topologySummary.firewalls },
          ].filter(({ value }) => value > 0).map(({ label, value }) => (
            <div key={label} className="flex items-center gap-1 rounded border border-navy-700/40 bg-navy-800/50 px-2 py-1">
              <span className="text-sm font-bold text-navy-100">{value}</span>
              <span className="text-xs text-navy-400">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Progress log */}
      {progress.length > 0 && (
        <div className="mt-2 max-h-36 overflow-y-auto rounded border border-navy-700/40 bg-navy-900/60 p-2 font-mono text-xs text-navy-300">
          {progress.map((line, i) => (
            <div
              key={i}
              className={i === progress.length - 1 && isActive ? "font-semibold text-teal-400" : ""}
            >
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Start / Re-sync Discovery form ───────────────────────────────────────────

function StartDiscoveryForm({
  engagementId,
  credentialId,
  hasCompleted,
}: {
  engagementId: string;
  credentialId: string;
  hasCompleted: boolean;
}) {
  const [state, action] = useActionState(startDiscovery, null);
  return (
    <form action={action} className="inline-flex flex-col items-start gap-1">
      <input type="hidden" name="engagementId" value={engagementId} />
      <input type="hidden" name="credentialId" value={credentialId} />
      {state?.error && (
        <span className="text-xs text-red-400">{state.error}</span>
      )}
      {hasCompleted ? (
        <SubmitButton
          loadingText="Syncing…"
          className="!bg-teal-700 hover:!bg-teal-600 focus:!ring-teal-500"
        >
          ↺ Re-sync data
        </SubmitButton>
      ) : (
        <SubmitButton loadingText="Starting…">Start discovery</SubmitButton>
      )}
    </form>
  );
}

// ─── Delete credential form ────────────────────────────────────────────────────

function DeleteCredentialButton({
  credentialId,
  engagementId,
  label,
}: {
  credentialId: string;
  engagementId: string;
  label: string;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [state, action, isPending] = useActionState(deleteCloudCredential, null);

  // After a successful delete, refresh the page via a normal GET instead of
  // triggering an RSC re-render from within the server action (which caused 500s).
  useEffect(() => {
    if (state?.deleted) router.refresh();
  }, [state, router]);

  if (confirming) {
    return (
      <form action={action} className="inline-flex flex-col items-start gap-1">
        <input type="hidden" name="credentialId" value={credentialId} />
        <input type="hidden" name="engagementId" value={engagementId} />
        {state?.error && (
          <span className="text-xs text-red-400">{state.error}</span>
        )}
        <div className="inline-flex items-center gap-1.5">
          <span className="text-xs text-navy-400">Remove {label}?</span>
          <button
            type="submit"
            disabled={isPending}
            className="rounded bg-red-900/40 px-2 py-0.5 text-xs font-semibold text-red-400 hover:bg-red-900/60 disabled:opacity-50"
          >
            {isPending ? "Removing…" : "Confirm"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            disabled={isPending}
            className="rounded bg-navy-700/40 px-2 py-0.5 text-xs text-navy-400 hover:bg-navy-700/60 disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </form>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setConfirming(true)}
      className="mt-1 inline-flex items-center gap-1 rounded border border-red-800/40 px-2 py-0.5 text-xs font-medium text-red-400 hover:bg-red-900/20 transition-colors"
    >
      <span>✕</span>
      <span>Remove</span>
    </button>
  );
}

interface ConnectionsPanelProps {
  engagementId: string;
  credentials: Pick<CloudCredential, "id" | "label" | "platform" | "tenantId" | "subscriptionIds">[];
  jobs: JobSummary[];
}

// ─── Per-credential card (manages live job state) ─────────────────────────────

function CredentialCard({
  cred,
  initialJobs,
  engagementId,
}: {
  cred: ConnectionsPanelProps["credentials"][number];
  initialJobs: JobSummary[];
  engagementId: string;
}) {
  // Live job map: starts from server-rendered data, updated by JobEntry polling.
  const [liveJobMap, setLiveJobMap] = useState<Map<string, JobSummary>>(
    () => new Map(initialJobs.map((j) => [j.id, j])),
  );

  const liveJobs = initialJobs.map((j) => liveJobMap.get(j.id) ?? j);
  const latestJob = liveJobs[0];
  const isActive = liveJobs.some((j) => ACTIVE_STATUSES.has(j.status));
  const hasCompleted = liveJobs.some((j) => j.status === "COMPLETED");

  function handleJobUpdate(updated: JobSummary) {
    setLiveJobMap((prev) => new Map(prev).set(updated.id, updated));
  }

  return (
    <div className="rounded-xl border border-navy-700/40 bg-navy-800/20 p-4">
      {/* Credential header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-navy-100">{cred.label}</p>
            {isActive && (
              <svg className="h-3.5 w-3.5 animate-spin text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
          </div>
          <p className="text-xs text-navy-400">
            {cred.platform} · Tenant: {cred.tenantId?.slice(0, 8)}…
            {cred.subscriptionIds.length > 0
              ? ` · ${cred.subscriptionIds.length} subscription(s)`
              : " · All subscriptions"}
          </p>

          {/* Last run + collapsible toggle */}
          {liveJobs.length > 0 && (
            <details className="mt-1 group/runs">
              <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-xs text-navy-400 hover:text-navy-200">
                <svg
                  className="h-3 w-3 transition-transform group-open/runs:rotate-90"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                {liveJobs.length} run{liveJobs.length !== 1 ? "s" : ""} ·{" "}
                Last:{" "}
                {latestJob.status === "COMPLETED"
                  ? `Completed ${new Date(latestJob.completedAt!).toLocaleDateString()}`
                  : latestJob.status === "FAILED"
                  ? "Failed"
                  : latestJob.status}
              </summary>
              <div className="mt-2 space-y-2">
                {liveJobs.map((job) => (
                  <JobEntry key={job.id} initial={job} onUpdate={handleJobUpdate} />
                ))}
              </div>
            </details>
          )}
          {liveJobs.length === 0 && (
            <p className="mt-1 text-xs text-navy-500">No runs yet</p>
          )}
        </div>

        {/* Actions column */}
        <div className="flex flex-col items-end gap-1 shrink-0">
          <StartDiscoveryForm
            engagementId={engagementId}
            credentialId={cred.id}
            hasCompleted={hasCompleted}
          />
          <DeleteCredentialButton
            credentialId={cred.id}
            engagementId={engagementId}
            label={cred.label}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export function ConnectionsPanel({
  engagementId,
  credentials,
  jobs,
}: ConnectionsPanelProps) {
  // Group jobs by credential, maintaining descending order
  const jobsByCredential = new Map<string, JobSummary[]>();
  for (const job of jobs) {
    if (!job.credentialId) continue;
    const existing = jobsByCredential.get(job.credentialId) ?? [];
    existing.push(job);
    jobsByCredential.set(job.credentialId, existing);
  }

  return (
    <div className="space-y-3">
      {credentials.length === 0 ? (
        <p className="text-sm text-navy-400">
          No connections yet. Add one in the section below.
        </p>
      ) : (
        credentials.map((cred) => (
          <CredentialCard
            key={cred.id}
            cred={cred}
            initialJobs={jobsByCredential.get(cred.id) ?? []}
            engagementId={engagementId}
          />
        ))
      )}
    </div>
  );
}
