import { cn } from "../../lib/utils";

type StatusBadgeVariant = "active" | "inactive" | "warning" | "error" | "info" | "manual";

const variantStyles: Record<StatusBadgeVariant, string> = {
  active: "border-green-200 bg-success-light text-success-foreground",
  inactive: "border-slate-200 bg-slate-100 text-slate-600",
  warning: "border-orange-200 bg-warning-light text-warning-foreground",
  error: "border-red-200 bg-danger-light text-danger-foreground",
  info: "border-blue-200 bg-brand-light text-blue-800",
  manual: "border-orange-200 bg-warning-light text-warning-foreground",
};

export function StatusBadge({
  label,
  variant = "info",
  className,
}: {
  label: string;
  variant?: StatusBadgeVariant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
        variantStyles[variant],
        className,
      )}
    >
      {label}
    </span>
  );
}

export function booleanActiveBadge(value: boolean) {
  return value ? (
    <StatusBadge label="Aktiv" variant="active" />
  ) : (
    <StatusBadge label="Inaktiv" variant="inactive" />
  );
}
