"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { label: "Overview", path: "" },
  { label: "Connections", path: "/connections" },
  { label: "Findings", path: "/findings" },
  { label: "Inventory", path: "/inventory" },
  { label: "Documents", path: "/documents" },
  { label: "Deliverables", path: "/deliverables" },
  { label: "Presentation", path: "/presentation" },
];

export function EngagementTabs({ engagementId }: { engagementId: string }) {
  const pathname = usePathname();
  const base = `/engagements/${engagementId}`;

  return (
    <div className="border-b border-gray-200">
      <nav className="-mb-px flex gap-1 overflow-x-auto">
        {TABS.map((tab) => {
          const href = `${base}${tab.path}`;
          // "Overview" is active only when we're exactly at the base path
          const isActive =
            tab.path === ""
              ? pathname === base
              : pathname === href || pathname.startsWith(href + "/");

          return (
            <Link
              key={tab.path}
              href={href}
              className={[
                "whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
              ].join(" ")}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
