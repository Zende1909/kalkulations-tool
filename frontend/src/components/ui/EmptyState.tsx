import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="app-card flex flex-col items-center justify-center px-6 py-14 text-center">
      <p className="text-section-title text-app-heading">{title}</p>
      {description ? <p className="mt-2 max-w-md text-body-lg text-app-muted">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
