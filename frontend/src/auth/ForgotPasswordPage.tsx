/**
 * Tenant Forgot Password V1 (docs/09, mirrors LoginPage's own layout/tone).
 * Public, pre-auth — no session, so no CSRF header, matching how
 * POST /auth/forgot-password itself is wired.
 *
 * The success state is always the same generic copy regardless of what
 * POST /auth/forgot-password actually did server-side (anti-enumeration —
 * see identity.service.request_password_reset()'s own docstring) — this
 * page must never distinguish "email sent" from "no such account" in any
 * way, including timing-sensitive UI states.
 */

import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div
        className="w-full max-w-sm rounded-lg bg-white p-8 shadow"
        aria-label={t("auth.forgot_password_title")}
      >
        <h1 className="mb-6 text-2xl font-bold text-slate-900">
          {t("auth.forgot_password_title")}
        </h1>

        {submitted ? (
          <>
            <p className="mb-6 text-sm text-slate-700" role="status">
              {t("auth.forgot_password_success")}
            </p>
            <Link to="/login" className="text-sm font-medium text-blue-700 hover:underline">
              {t("auth.back_to_login")}
            </Link>
          </>
        ) : (
          <form onSubmit={onSubmit}>
            <p className="mb-4 text-sm text-slate-600">{t("auth.forgot_password_hint")}</p>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
              {t("auth.email")}
            </label>
            <input
              id="email"
              type="email"
              required
              autoFocus
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
              className="mb-4 w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {submitting ? t("common.loading") : t("auth.forgot_password_submit")}
            </button>
            <Link to="/login" className="text-sm font-medium text-blue-700 hover:underline">
              {t("auth.back_to_login")}
            </Link>
          </form>
        )}
      </div>
    </main>
  );
}
