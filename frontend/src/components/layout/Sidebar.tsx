import { NavLink, useLocation } from "react-router-dom";
import { useState } from "react";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  {
    label: "Stammdaten",
    children: [
      { to: "/stammdaten/materialien", label: "Materialien" },
      { to: "/stammdaten/maschinen", label: "Maschinen" },
      { to: "/stammdaten/lohnkosten", label: "Lohnkosten" },
      { to: "/stammdaten/kaufteile", label: "Kaufteile" },
      { to: "/stammdaten/zuschlagssaetze", label: "Zuschlagssätze" },
    ],
  },
  { to: "/spritzguss", label: "Spritzguss-Kalkulation" },
  { to: "/veredelung", label: "Veredelung" },
  { to: "/baugruppen", label: "Baugruppen" },
  { to: "/investitionen", label: "Investitionen" },
];

function linkClass(isActive: boolean) {
  return [
    "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-sidebar-active text-white" : "text-slate-300 hover:bg-sidebar-hover hover:text-white",
  ].join(" ");
}

export function Sidebar() {
  const location = useLocation();
  const isStammdatenActive = location.pathname.startsWith("/stammdaten");
  const [stammdatenOpen, setStammdatenOpen] = useState(isStammdatenActive);

  return (
    <aside className="flex w-64 flex-col bg-sidebar text-white">
      <div className="border-b border-slate-700 px-4 py-5">
        <h1 className="text-lg font-semibold">Kalkulations-Tool</h1>
        <p className="text-xs text-slate-400">Kunststoffmodule Automotive</p>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map((item) => {
          if ("children" in item) {
            return (
              <div key={item.label}>
                <button
                  type="button"
                  onClick={() => setStammdatenOpen((open) => !open)}
                  className={[
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isStammdatenActive
                      ? "bg-sidebar-active text-white"
                      : "text-slate-300 hover:bg-sidebar-hover hover:text-white",
                  ].join(" ")}
                >
                  {item.label}
                  <span className="text-xs">{stammdatenOpen ? "▾" : "▸"}</span>
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
