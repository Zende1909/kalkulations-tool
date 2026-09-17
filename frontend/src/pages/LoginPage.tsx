import { FormEvent, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";
import { BrandLogo } from "../components/BrandLogo";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { Button } from "../components/ui/Button";
import { ValidationMessage } from "../components/ui/ValidationMessage";
import { PRODUCT_NAME } from "../branding";
import { useLocale } from "../i18n";

export function LoginPage() {
  const { user, login } = useAuth();
  const { t } = useLocale();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  const [email, setEmail] = useState("j.zende@zende-consultant.de");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = `${t("auth.title")} · ${PRODUCT_NAME}`;
  }, [t]);

  if (user) {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login({ email, password });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t("auth.failed");
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-cyan-50 via-white to-lime-50 px-4 py-8">
      <div className="w-full max-w-md app-card p-8">
        <div className="mb-4 flex justify-end">
          <LanguageSwitcher />
        </div>
        <div className="mb-6 border-b border-app-border pb-5">
          <BrandLogo size="lg" />
          <h1 className="mt-4 text-page-title text-app-heading">{PRODUCT_NAME}</h1>
          <p className="mt-2 text-body-lg text-app-muted">{t("auth.subtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="block text-body-lg font-medium text-app-heading">
              {t("auth.email")}
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="app-input"
              autoComplete="username"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-body-lg font-medium text-app-heading">
              {t("auth.password")}
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="app-input"
              autoComplete="current-password"
            />
          </div>

          {error ? <ValidationMessage variant="error">{error}</ValidationMessage> : null}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? t("auth.submitting") : t("auth.submit")}
          </Button>
        </form>
      </div>
    </div>
  );
}
