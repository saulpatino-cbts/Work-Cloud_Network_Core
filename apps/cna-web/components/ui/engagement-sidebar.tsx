"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  {
    path: "",
    label: "Overview",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    path: "/connections",
    label: "Connections",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    path: "/findings",
    label: "Findings",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      </svg>
    ),
  },
  {
    path: "/inventory",
    label: "Inventory",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
      </svg>
    ),
  },
  {
    path: "/documents",
    label: "Documents",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    path: "/deliverables",
    label: "Deliverables",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
      </svg>
    ),
  },
  {
    path: "/presentation",
    label: "Presentation",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 13v-1m4 1v-3m4 3V8M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
      </svg>
    ),
  },
];

const STORAGE_KEY = "cna-sidebar-collapsed";

export function EngagementSidebar({ engagementId }: { engagementId: string }) {
  const pathname = usePathname();
  const base = `/engagements/${engagementId}`;

  // Read persisted collapse state from localStorage
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
      try { localStorage.setItem(STORAGE_KEY, String(next)); } catch { /* ignore */ }
      return next;
    });
  }

  // Avoid hydration mismatch — render collapsed=false on server, then snap to saved state
  const isCollapsed = mounted ? collapsed : false;

  return (
    <aside
      className={[
        "relative flex-shrink-0 transition-all duration-200",
        isCollapsed ? "w-12" : "w-52",
      ].join(" ")}
    >
      {/* Inner panel */}
      <div
        className={[
          "sticky top-0 flex h-full flex-col rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden",
          isCollapsed ? "w-12" : "w-52",
        ].join(" ")}
      >
        {/* Toggle button */}
        <div className="flex items-center justify-between border-b border-gray-100 px-2 py-2.5">
          {!isCollapsed && (
            <span className="pl-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
              Navigation
            </span>
          )}
          <button
            onClick={toggle}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={[
              "flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors",
              isCollapsed ? "mx-auto" : "ml-auto",
            ].join(" ")}
          >
            {isCollapsed ? (
              // Chevron right (expand)
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            ) : (
              // Chevron left (collapse)
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            )}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex flex-col gap-0.5 p-1.5">
          {NAV_ITEMS.map((item) => {
            const href = `${base}${item.path}`;
            const isActive =
              item.path === ""
                ? pathname === base
                : pathname === href || pathname.startsWith(href + "/");

            return (
              <Link
                key={item.path}
                href={href}
                title={isCollapsed ? item.label : undefined}
                className={[
                  "flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
                ].join(" ")}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                {!isCollapsed && (
                  <span className="truncate">{item.label}</span>
                )}
                {isActive && !isCollapsed && (
                  <span className="ml-auto h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-600" />
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
