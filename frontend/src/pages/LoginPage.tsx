import { FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { ValidationMessage } from "../components/ui/ValidationMessage";

export function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  const [email, setEmail] = useState("j.zende@zende-consultant.de");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
      const message =
        err instanceof ApiError ? err.message : "Anmeldung fehlgeschlagen. Bitte erneut versuchen.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-app-surface px-4 py-8">
      <div className="w-full max-w-md app-card p-8">
        <div className="mb-6 border-b border-app-border pb-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand">ZENDE Consultant</p>
          <h1 className="mt-1 text-page-title text-app-heading">Kalkulations-Tool</h1>
          <p className="mt-2 text-body-lg text-app-muted">
            Industrielles Kunststoff-Kalkulationstool – bitte melden Sie sich an.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="block text-body-lg font-medium text-app-heading">
              E-Mail
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
              Passwort
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

          <Button type="submit" disabled={submitting} className="w-full" size="lg">
            {submitting ? "Anmelden…" : "Anmelden"}
          </Button>
        </form>
      </div>
    </div>
  );
}
