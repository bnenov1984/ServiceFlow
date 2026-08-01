import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { ApiError, api, setVendorCsrfToken } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { VendorMe } from "./types";

export function VendorLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const me = await api.post<VendorMe>("/platform-admin/auth/login", { email, password });
      // Set the CSRF token directly rather than relying solely on
      // VendorAuthContext's `useEffect` to pick it up from the query cache
      // - see auth/LoginPage.tsx's identical fix for why that hand-off is
      // race-prone around removeQueries()/setQueryData().
      setVendorCsrfToken(me.csrf_token);
      // Seed vendorMe BEFORE removing anything else, and never remove it
      // itself in the same pass - see auth/LoginPage.tsx's identical fix
      // for the stale-then-correct render window this closes (destroying
      // an actively-observed query's state, even briefly, is visible to
      // its mounted observer).
      queryClient.setQueryData(queryKeys.vendorMe, me);
      // Logging in over an already-authenticated vendor session (switching
      // admins mid-tab without an explicit logout) must not leave stale
      // ["vendor", ...] cache visible - same fix as auth/LoginPage.tsx's
      // tenant-side login, and scoped rather than a full clear() for the
      // same reason VendorAuthContext.logout() already gives: a tenant
      // session can be alive in the same tab and must not be wiped.
      queryClient.removeQueries({
        predicate: (q) => q.queryKey[0] === "vendor" && q.queryKey[1] !== "me",
      });
      const next = new URLSearchParams(location.search).get("next") ?? "/vendor/companies";
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
        aria-label={t("vendor.title")}
      >
        <h1 className="mb-6 text-2xl font-bold text-slate-900">{t("vendor.title")}</h1>
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="vendor-email">
          {t("auth.email")}
        </label>
        <input
          id="vendor-email"
          type="email"
          required
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
        />
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="vendor-password">
          {t("auth.password")}
        </label>
        <input
          id="vendor-password"
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
          {submitting ? t("common.loading") : t("vendor.login_submit")}
        </button>
      </form>
    </main>
  );
}
