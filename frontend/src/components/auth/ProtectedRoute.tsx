import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useT } from "../../i18n";

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const t = useT();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-app-surface">
        <div className="app-card px-8 py-6 text-body-lg text-app-muted">{t("auth.checking")}</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
