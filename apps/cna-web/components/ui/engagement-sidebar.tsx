"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  {
    path: "",
    label: "Overview",
    icon: (
      // WAI-01 / W3C-02: aria-hidden on decorative icon; label conveyed by adjacent text or Link aria-label
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    path: "/connections",
    label: "Connections",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    path: "/inventory",
    label: "Inventory",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
      </svg>
    ),
  },
  {
    path: "/findings",
    label: "Findings",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      </svg>
    ),
  },
  {
    path: "/analysis",
    label: "Analysis",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    path: "/deliverables",
    label: "Assessments",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
  },
  {
    path: "/diagram",
    label: "Diagram",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h7m-7 4h10M5 4h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z" />
      </svg>
    ),
  },
  {
    path: "/documents",
    label: "Documents",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    path: "/presentation",
    label: "Presentation",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 13v-1m4 1v-3m4 3V8M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
      </svg>
    ),
  },
  {
    path: "/client-deliverables",
    label: "Deliverables",
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
    ),
  },
];

const STORAGE_KEY = "cna-sidebar-collapsed";

export function EngagementSidebar({ engagementId }: { engagementId: string }) {
  const pathname = usePathname();
  const base = `/engagements/${engagementId}`;

  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "true") setCollapsed(true);
    } catch {
      // localStorage not available
    }
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  const isCollapsed = mounted ? collapsed : false;

  return (
    // WAI-17: aria-label distinguishes this landmark from the header nav
    <aside
      aria-label="Engagement navigation"
      className={[
        "relative flex-shrink-0 transition-all duration-200",
        isCollapsed ? "w-[3.25rem]" : "w-52",
      ].join(" ")}
    >
      <div
        className={[
          /* glass panel */
          "glass sticky top-20 flex flex-col overflow-hidden",
          isCollapsed ? "w-[3.25rem]" : "w-52",
        ].join(" ")}
      >
        {/* ── Toggle row ── */}
        <div className="flex items-center justify-between border-b border-navy-100/40 px-2 py-2.5 dark:border-navy-700/40">
          {!isCollapsed && (
            <span className="label-caps pl-1 text-navy-300 dark:text-navy-500" aria-hidden="true">
              Navigation
            </span>
          )}
          {/* WAI-02: aria-label replaces title; aria-expanded + aria-controls communicate state */}
          <button
            type="button"
            onClick={toggle}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            {...{ "aria-expanded": !isCollapsed }}
            aria-controls="engagement-nav"
            className={[
              "flex h-7 w-7 items-center justify-center rounded-lg text-navy-300 transition-colors hover:bg-teal-50 hover:text-teal-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-1 dark:text-navy-500 dark:hover:bg-teal-900/30 dark:hover:text-teal-400",
              isCollapsed ? "mx-auto" : "ml-auto",
            ].join(" ")}
          >
            {/* W3C-02: decorative chevron SVG hidden from AT */}
            {isCollapsed ? (
              <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            ) : (
              <svg aria-hidden="true" focusable="false" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            )}
          </button>
        </div>

        {/* WAI-17: id matches aria-controls on toggle button; aria-label names this nav region */}
        <nav id="engagement-nav" aria-label="Engagement sections" className="flex flex-col gap-0.5 p-1.5">
          {NAV_ITEMS.map((item) => {
            const href = `${base}${item.path}`;
            const isActive =
              item.path === ""
                ? pathname === base
                : pathname === href || pathname.startsWith(href + "/");

            return (
              // WAI-01: When collapsed, icon is the only visible content — aria-label provides the name.
              // When expanded, the visible text label makes aria-label redundant (omit to avoid duplication).
              <Link
                key={item.path}
                href={href}
                aria-label={isCollapsed ? item.label : undefined}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-1",
                  isActive
                    ? "nav-active font-semibold"
                    : "text-navy-500 hover:bg-navy-50/60 hover:text-navy-800 dark:text-navy-300 dark:hover:bg-navy-800/40 dark:hover:text-navy-100",
                ].join(" ")}
              >
                <span className="flex-shrink-0" aria-hidden="true">{item.icon}</span>
                {!isCollapsed && (
                  <span className="truncate">{item.label}</span>
                )}
                {isActive && !isCollapsed && (
                  <span className="ml-auto h-1.5 w-1.5 flex-shrink-0 rounded-full bg-teal-500" aria-hidden="true" />
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
