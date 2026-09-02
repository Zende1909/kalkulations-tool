import { Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { getPageDescription, getPageTitle } from "./pageTitle";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);
  const pageDescription = getPageDescription(location.pathname);

  return (
    <div className="flex min-h-screen bg-app-surface">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-app-border bg-white/95 px-6 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-[1600px] flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-brand">Bereich</p>
              <h2 className="truncate text-xl font-bold text-app-heading">{pageTitle}</h2>
              {pageDescription ? (
                <p className="mt-0.5 line-clamp-2 text-sm text-app-muted">{pageDescription}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-xs font-medium uppercase tracking-wide text-app-muted">
                  Angemeldet
                </p>
                <p className="text-sm font-semibold text-app-heading">{user?.email}</p>
              </div>
              <StatusBadge label={user?.role ?? "–"} variant="info" />
              <Button variant="secondary" size="sm" onClick={logout}>
                Abmelden
              </Button>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto px-4 py-6 sm:px-6">
          <div className="mx-auto max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
