import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { useAuth, type Me } from "./AuthContext";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post<Me>("/auth/login", {
        email,
        password,
        device_label: navigator.platform ?? "",
      });
      await refresh();
      const next = new URLSearchParams(location.search).get("next") ?? "/";
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-lg bg-white p-8 shadow"
        aria-label={t("auth.title")}
      >
        <h1 className="mb-6 text-2xl font-bold text-slate-900">{t("app.name")}</h1>
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
          {t("auth.email")}
        </label>
        <input
          id="email"
          type="email"
          required
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="password">
          {t("auth.password")}
        </label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
        {error && (
          <p role="alert" className="mb-4 text-sm text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
        >
          {submitting ? t("common.loading") : t("auth.submit")}
        </button>
      </form>
    </main>
  );
}
