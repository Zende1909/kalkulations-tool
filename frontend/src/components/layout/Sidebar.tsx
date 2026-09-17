import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import {
  Briefcase,
  ChartLineUp,
  Cube,
  Factory,
  GearSix,
  Package,
  SquaresFour,
  Stack,
  TrendUp,
  UsersThree,
} from "@phosphor-icons/react";

import { useActiveProject } from "../../context/ActiveProjectContext";
import { useT } from "../../i18n";
import { cn } from "../../lib/utils";
import { BrandLogo } from "../BrandLogo";
import { CustomerProjectSelector } from "../hierarchy/CustomerProjectSelector";
import { Button } from "../ui/Button";
import { isStammdatenSectionPath, navItems, type NavItem } from "./navConfig";

export { isStammdatenSectionPath, navItems } from "./navConfig";

const iconClass = "size-4 shrink-0 opacity-90";

function navIcon(item: NavItem): ReactNode {
  if ("children" in item) {
    return <GearSix className={iconClass} weight="duotone" aria-hidden />;
  }
  switch (item.to) {
    case "/":
      return <ChartLineUp className={iconClass} weight="duotone" aria-hidden />;
    case "/spritzguss":
      return <Cube className={iconClass} weight="duotone" aria-hidden />;
    case "/stammdaten/kaufteile":
      return <Package className={iconClass} weight="duotone" aria-hidden />;
    case "/veredelung":
      return <Factory className={iconClass} weight="duotone" aria-hidden />;
    case "/baugruppen":
      return <Stack className={iconClass} weight="duotone" aria-hidden />;
    case "/maschinenauslastung":
      return <SquaresFour className={iconClass} weight="duotone" aria-hidden />;
    case "/investitionen":
      return <TrendUp className={iconClass} weight="duotone" aria-hidden />;
    case "/business-case":
      return <Briefcase className={iconClass} weight="duotone" aria-hidden />;
    default:
      return <UsersThree className={iconClass} weight="duotone" aria-hidden />;
  }
}

function linkClass(isActive: boolean) {
  return cn(
    "flex items-center gap-2.5 rounded-app px-3 py-2.5 text-body-lg font-medium transition-colors",
    isActive
      ? "bg-sidebar-active text-sidebar-active-foreground shadow-sm"
      : "text-sidebar-foreground hover:bg-sidebar-hover hover:text-white",
  );
}

export function Sidebar() {
  const t = useT();
  const location = useLocation();
  const isStammdatenActive = isStammdatenSectionPath(location.pathname);
  const [stammdatenOpen, setStammdatenOpen] = useState(isStammdatenActive);
  const { selection, isComplete, setSelection, clearSelection } = useActiveProject();

  useEffect(() => {
    if (isStammdatenActive) {
      setStammdatenOpen(true);
    }
  }, [isStammdatenActive]);

  const hasAnySelection =
    selection.customer_id != null || selection.program_id != null || selection.project_id != null;

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="border-b border-sidebar-border px-5 py-5">
        <BrandLogo size="sm" onDark showWordmark />
        <p className="mt-2 text-sm text-sidebar-muted">{t("branding.tagline")}</p>

        <div
          className="mt-4 rounded-app border border-sidebar-border bg-black/20 p-3"
          data-testid="active-project-bar"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-sidebar-muted">
              {t("project.activeProject")}
            </p>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                isComplete
                  ? "bg-emerald-500/20 text-emerald-200"
                  : "bg-white/10 text-sidebar-muted",
              )}
            >
              {isComplete ? t("project.filterActive") : t("project.allProjects")}
            </span>
          </div>
          <CustomerProjectSelector compact value={selection} onChange={setSelection} />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-2 w-full"
            onClick={clearSelection}
            disabled={!hasAnySelection}
          >
            {t("project.allProjects")}
          </Button>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Main navigation">
        {navItems.map((item) => {
          if ("children" in item) {
            return (
              <div key={item.labelKey}>
                <button
                  type="button"
                  onClick={() => setStammdatenOpen((open) => !open)}
                  aria-expanded={stammdatenOpen}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-app px-3 py-2.5 text-body-lg font-semibold transition-colors",
                    isStammdatenActive
                      ? "bg-sidebar-active text-sidebar-active-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-hover hover:text-white",
                  )}
                >
                  <span className="flex items-center gap-2.5">
                    {navIcon(item)}
                    {t(item.labelKey)}
                  </span>
                  <span className="text-xs opacity-80" aria-hidden>
                    {stammdatenOpen ? "▾" : "▸"}
                  </span>
                </button>
                {stammdatenOpen && item.children && (
                  <div className="ml-3 mt-1 space-y-0.5 border-l-2 border-sidebar-border pl-3">
                    {item.children.map((child) => (
                      <NavLink
                        key={child.to}
                        to={child.to}
                        className={({ isActive }) => linkClass(isActive)}
                      >
                        {t(child.labelKey)}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => linkClass(isActive)}
            >
              {navIcon(item)}
              {t(item.labelKey)}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
