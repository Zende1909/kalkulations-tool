import { cn } from "../../lib/utils";

type ValidationVariant = "error" | "success" | "warning" | "info";

const styles: Record<ValidationVariant, string> = {
  error: "border-red-200 bg-danger-light text-danger-foreground",
  success: "border-green-200 bg-success-light text-success-foreground",
  warning: "border-orange-200 bg-warning-light text-warning-foreground",
  info: "border-blue-200 bg-brand-light text-blue-900",
};

export function ValidationMessage({
  variant = "error",
  children,
  className,
}: {
  variant?: ValidationVariant;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn(
        "rounded-app border px-4 py-3 text-body-lg",
        styles[variant],
        className,
      )}
    >
      {children}
    </div>
  );
}
