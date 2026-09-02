import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

export function PageHeader({
  title,
  description,
  meta,
  actions,
  className,
}: {
  title: string;
  description?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "mb-6 flex flex-col gap-4 border-b border-app-border pb-5 lg:flex-row lg:items-start lg:justify-between",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-page-title text-app-heading">{title}</h1>
        {description ? (
          <p className="mt-1.5 max-w-3xl text-body-lg text-app-muted">{description}</p>
        ) : null}
        {meta ? <div className="mt-2 text-sm text-app-muted">{meta}</div> : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  );
}
