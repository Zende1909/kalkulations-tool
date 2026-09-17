import { Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";

import { PRODUCT_NAME } from "../../branding";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../i18n";
import { LanguageSwitcher } from "../LanguageSwitcher";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { getPageDescriptionKey, getPageTitleKey } from "./pageTitle";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const location = useLocation();
  const pageTitle = t(getPageTitleKey(location.pathname));
  const descriptionKey = getPageDescriptionKey(location.pathname);
  const pageDescription = descriptionKey ? t(descriptionKey) : undefined;

  useEffect(() => {
    document.title = pageTitle === PRODUCT_NAME ? PRODUCT_NAME : `${pageTitle} · ${PRODUCT_NAME}`;
  }, [pageTitle]);

  return (
    <div className="flex min-h-screen bg-app-surface">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-app-border bg-white/95 px-6 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-[1600px] flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-brand">
                {t("common.section")}
              </p>
              <h2 className="truncate text-xl font-bold text-app-heading">{pageTitle}</h2>
              {pageDescription ? (
                <p className="mt-0.5 line-clamp-2 text-sm text-app-muted">{pageDescription}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-xs font-medium uppercase tracking-wide text-app-muted">
                  {t("common.signedIn")}
                </p>
                <p className="text-sm font-semibold text-app-heading">{user?.email}</p>
              </div>
              <StatusBadge label={user?.role ?? "–"} variant="info" />
              <LanguageSwitcher />
              <Button variant="secondary" size="sm" onClick={logout}>
                {t("common.logout")}
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
