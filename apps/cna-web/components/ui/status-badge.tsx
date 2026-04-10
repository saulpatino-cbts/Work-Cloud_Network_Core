const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  DISCOVERY: "bg-blue-100 text-blue-700",
  ANALYSIS: "bg-yellow-100 text-yellow-700",
  REVIEW: "bg-purple-100 text-purple-700",
  DELIVERED: "bg-green-100 text-green-700",
};

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-700",
  HIGH: "bg-orange-100 text-orange-700",
  MEDIUM: "bg-yellow-100 text-yellow-700",
  LOW: "bg-blue-100 text-blue-700",
  INFORMATIONAL: "bg-gray-100 text-gray-600",
};

const DOCTYPE_COLORS: Record<string, string> = {
  CLIENT_ARCHITECTURE: "bg-indigo-100 text-indigo-700",
  COMPLIANCE_FRAMEWORK: "bg-purple-100 text-purple-700",
  NETWORK_DIAGRAM: "bg-cyan-100 text-cyan-700",
  CONFIGURATION_EXPORT: "bg-teal-100 text-teal-700",
  OTHER: "bg-gray-100 text-gray-600",
};

const LABELS: Record<string, string> = {
  DRAFT: "Draft",
  DISCOVERY: "Discovery",
  ANALYSIS: "Analysis",
  REVIEW: "Review",
  DELIVERED: "Delivered",
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
  INFORMATIONAL: "Info",
  CLIENT_ARCHITECTURE: "Architecture",
  COMPLIANCE_FRAMEWORK: "Compliance",
  NETWORK_DIAGRAM: "Diagram",
  CONFIGURATION_EXPORT: "Config",
  OTHER: "Other",
};

interface StatusBadgeProps {
  value: string;
  variant: "status" | "severity" | "doctype";
}

export function StatusBadge({ value, variant }: StatusBadgeProps) {
  const colorMap =
    variant === "status"
      ? STATUS_COLORS
      : variant === "severity"
        ? SEVERITY_COLORS
        : DOCTYPE_COLORS;

  const color = colorMap[value] ?? "bg-gray-100 text-gray-600";
  const label = LABELS[value] ?? value;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}
    >
      {label}
    </span>
  );
}
