import type { InputHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export function InputWithUnit({
  unit,
  className,
  inputClassName,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  unit: string;
  inputClassName?: string;
}) {
  return (
    <div className={cn("relative", className)}>
      <input className={cn("app-input pr-14", inputClassName)} {...props} />
      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-medium text-app-muted">
        {unit}
      </span>
    </div>
  );
}
