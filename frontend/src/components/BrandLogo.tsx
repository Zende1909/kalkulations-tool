import { COMPANY_BRAND, LOGO_SRC, PRODUCT_NAME } from "../branding";
import { cn } from "../lib/utils";

type BrandLogoProps = {
  /** Kompakt für Sidebar; groß für Login */
  size?: "sm" | "md" | "lg";
  /** Weißer Hintergrund für dunkle Flächen (Logo hat dunkle Schrift) */
  onDark?: boolean;
  className?: string;
  showWordmark?: boolean;
};

const sizeClass = {
  sm: "h-9",
  md: "h-12",
  lg: "h-16",
} as const;

export function BrandLogo({
  size = "md",
  onDark = false,
  className,
  showWordmark = false,
}: BrandLogoProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        className={cn(
          "flex shrink-0 items-center justify-center overflow-hidden rounded-app",
          onDark ? "bg-white px-2 py-1.5 shadow-sm" : "bg-transparent",
        )}
      >
        <img
          src={LOGO_SRC}
          alt={`${COMPANY_BRAND} Logo`}
          className={cn("w-auto object-contain", sizeClass[size])}
        />
      </div>
      {showWordmark ? (
        <div className="min-w-0">
          <p
            className={cn(
              "truncate text-xl font-bold tracking-tight",
              onDark ? "text-white" : "text-app-heading",
            )}
          >
            {PRODUCT_NAME}
          </p>
          <p className={cn("truncate text-xs", onDark ? "text-sidebar-muted" : "text-app-muted")}>
            {COMPANY_BRAND}
          </p>
        </div>
      ) : null}
    </div>
  );
}
