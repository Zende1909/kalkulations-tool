import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";

import { isStammdatenSectionPath, navItems } from "./navConfig";

export { isStammdatenSectionPath, navItems } from "./navConfig";

function linkClass(isActive: boolean) {
  return [
    "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-sidebar-active text-white" : "text-slate-300 hover:bg-sidebar-hover hover:text-white",
  ].join(" ");
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
    <aside className="flex w-64 shrink-0 flex-col bg-sidebar text-white">
      <div className="border-b border-slate-700 px-4 py-5">
        <h1 className="text-lg font-semibold">Kalkulations-Tool</h1>
        <p className="text-xs text-slate-400">Kunststoffmodule Automotive</p>
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
                  className={[
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isStammdatenActive
                      ? "bg-sidebar-active text-white"
                      : "text-slate-300 hover:bg-sidebar-hover hover:text-white",
                  ].join(" ")}
                >
                  {item.label}
                  <span className="text-xs" aria-hidden>
                    {stammdatenOpen ? "▾" : "▸"}
                  </span>
                </button>
                {stammdatenOpen && item.children && (
                  <div className="ml-2 mt-1 space-y-1 border-l border-slate-600 pl-2">
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
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
