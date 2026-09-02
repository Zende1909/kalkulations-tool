import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

export function ResultCard({
  label,
  value,
  hint,
  tone = "neutral",
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "brand";
  className?: string;
}) {
  const toneStyles = {
    neutral: "border-app-border bg-white",
    success: "border-green-200 bg-success-light",
    warning: "border-orange-200 bg-warning-light",
    danger: "border-red-200 bg-danger-light",
    brand: "border-blue-200 bg-brand-light",
  } as const;

  return (
    <div className={cn("app-card p-4", toneStyles[tone], className)}>
      <p className="text-xs font-semibold uppercase tracking-wide text-app-muted">{label}</p>
      <p className="mt-1 text-xl font-bold text-app-heading">{value}</p>
      {hint ? <p className="mt-1 text-sm text-app-muted">{hint}</p> : null}
    </div>
  );
}
