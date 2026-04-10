"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { startDiscovery } from "../discovery/actions";
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
  CRITICAL: "bg-red-100 text-red-700",
  HIGH: "bg-orange-100 text-orange-700",
  MEDIUM: "bg-yellow-100 text-yellow-800",
  LOW: "bg-blue-100 text-blue-700",
  INFORMATIONAL: "bg-gray-100 text-gray-600",
};

// ─── Job log row ──────────────────────────────────────────────────────────────

function JobLogRow({ initial }: { initial: JobSummary }) {
  const [job, setJob] = useState(initial);
  // All runs start collapsed — user expands to see details
  const [expanded, setExpanded] = useState(false);
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

  // Sort severity counts in canonical order for display
  const severityCounts = SEVERITY_ORDER.map((sev) => {
    const found = job.findingsBySeverity?.find((s) => s.severity === sev);
    return { severity: sev, count: found?.count ?? 0 };
  }).filter((s) => s.count > 0);

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
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            {expanded ? "Hide ▲" : "Show details ▼"}
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

      {/* Expanded content */}
      {expanded && (
        <div className="mt-3 space-y-3">
          {/* Topology summary (COMPLETED only) */}
          {isCompleted && job.topologySummary && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                What was discovered
              </p>
              <div className="flex flex-wrap gap-2">
                {[
                  { label: "VNets", value: job.topologySummary.vnets },
                  { label: "Subnets", value: job.topologySummary.subnets },
                  { label: "Firewalls", value: job.topologySummary.firewalls },
                  { label: "App Gateways", value: job.topologySummary.appGateways },
                  { label: "DNS Zones", value: job.topologySummary.dnsZones },
                  { label: "ExpressRoutes", value: job.topologySummary.expressRoutes },
                ].map(({ label, value }) => (
                  <div
                    key={label}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5"
                  >
                    <span className="text-sm font-bold text-gray-800">{value}</span>
                    <span className="text-xs text-gray-500">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Findings by severity (COMPLETED only) */}
          {isCompleted && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                Findings by severity
              </p>
              {severityCounts.length === 0 ? (
                <p className="text-xs text-gray-400">No findings recorded yet.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {severityCounts.map(({ severity, count }) => (
                    <span
                      key={severity}
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${SEVERITY_STYLE[severity] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {severity}: {count}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Progress log */}
          {progress.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                Progress log
              </p>
              <div className="max-h-48 overflow-y-auto rounded border border-gray-200 bg-white p-3 font-mono text-xs text-gray-600">
                {progress.map((line, i) => (
                  <div
                    key={i}
                    className={i === progress.length - 1 && isActive ? "font-semibold text-blue-600" : ""}
                  >
                    {line}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </li>
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
    <form action={action} className="inline-flex items-center gap-2">
      <input type="hidden" name="engagementId" value={engagementId} />
      <input type="hidden" name="credentialId" value={credentialId} />
      {state?.error && (
        <span className="text-xs text-red-600">{state.error}</span>
      )}
      {hasCompleted ? (
        <SubmitButton
          loadingText="Syncing…"
          className="!bg-green-600 hover:!bg-green-700 focus:!ring-green-500"
        >
          ↺ Re-sync data
        </SubmitButton>
      ) : (
        <SubmitButton loadingText="Starting…">Start discovery</SubmitButton>
      )}
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
            const hasCompleted = lastJob?.status === "COMPLETED";
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
                  hasCompleted={hasCompleted}
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
