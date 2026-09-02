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

import { cn } from "../../lib/utils";
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
  const location = useLocation();
  const isStammdatenActive = isStammdatenSectionPath(location.pathname);
  const [stammdatenOpen, setStammdatenOpen] = useState(isStammdatenActive);

  useEffect(() => {
    if (isStammdatenActive) {
      setStammdatenOpen(true);
    }
  }, [isStammdatenActive]);

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="border-b border-sidebar-border px-5 py-6">
        <h1 className="text-xl font-bold tracking-tight text-white">Kalkulations-Tool</h1>
        <p className="mt-1 text-sm text-sidebar-muted">Kunststoffmodule Automotive</p>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Hauptnavigation">
        {navItems.map((item) => {
          if ("children" in item) {
            return (
              <div key={item.label}>
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
                    {item.label}
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
                        {child.label}
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
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
