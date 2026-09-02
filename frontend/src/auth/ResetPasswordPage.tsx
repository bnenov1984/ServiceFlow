/**
 * Tenant Forgot Password V1 — the "enter new password" half. Public,
 * pre-auth (no CSRF, matching POST /auth/reset-password itself).
 *
 * Deliberately does NOT log the user in on success: identity.service.
 * reset_password() already revoked every existing session for this user,
 * so silently starting a brand new one here would undercut that — the
 * user re-enters their new password at a real login prompt instead.
 */

import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";

const PASSWORD_MIN = 12;
const PASSWORD_MAX = 200;

export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = new URLSearchParams(location.search).get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [succeeded, setSucceeded] = useState(false);

  const validationError = (): string | null => {
    if (!token) return t("auth.reset_password_missing_token");
    if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
      return t("auth.reset_password_length_hint", {
        min: String(PASSWORD_MIN), max: String(PASSWORD_MAX),
      });
    }
    if (password !== confirmPassword) return t("auth.reset_password_mismatch");
    return null;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const localError = validationError();
    if (localError) {
      setError(localError);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      setSucceeded(true);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-2xl font-bold text-slate-900">
          {t("auth.reset_password_title")}
        </h1>

        {succeeded ? (
          <>
            <p className="mb-6 text-sm text-slate-700" role="status">
              {t("auth.reset_password_success")}
            </p>
            <button
              type="button"
              onClick={() => navigate("/login", { replace: true })}
              className="w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 min-h-touch"
            >
              {t("auth.back_to_login")}
            </button>
          </>
        ) : (
          <form onSubmit={onSubmit}>
            {!token && (
              <p role="alert" className="mb-4 text-sm text-red-700">
                {t("auth.reset_password_missing_token")}
              </p>
            )}
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="password">
              {t("auth.reset_password_new_password")}
            </label>
            <input
              id="password"
              type="password"
              required
              autoFocus
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="confirm-password"
            >
              {t("auth.reset_password_confirm")}
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
            />
            {error && (
              <div className="mb-4 flex flex-col gap-1">
                <p role="alert" className="text-sm text-red-700">{error}</p>
                <Link to="/forgot-password" className="text-sm font-medium text-blue-700 hover:underline">
                  {t("auth.reset_password_request_new_link")}
                </Link>
              </div>
            )}
            <button
              type="submit"
              disabled={submitting || !token}
              className="mb-4 w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
            >
              {submitting ? t("common.loading") : t("auth.reset_password_submit")}
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
