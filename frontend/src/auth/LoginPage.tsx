import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { ApiError, api, setCsrfToken } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { waitForQueryNotifications } from "../lib/queryNotify";
import { clearLastApp } from "../shell/lastApp";
import type { Me } from "./AuthContext";

/** A `?next=` deep link captured while logged in as a *different* company
 * (e.g. RequireAuth redirecting from "/ps") is meaningless for whichever
 * company just authenticated - "/ps" is PropertyFlow-only, everything else
 * other than "/settings/*" (a Core feature, gated by neither module) is
 * RepairFlow's. Falls back to "/", whose own IndexRoute (App.tsx) already
 * picks the right home page from the fresh active_modules. */
function isSafeNext(next: string, activeModules: string[]): boolean {
  if (next.startsWith("/ps")) return activeModules.includes("professional-services");
  if (next === "/" || next.startsWith("/settings")) return true;
  return activeModules.includes("repairflow");
}

export function LoginPage() {
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
      const me = await api.post<Me>("/auth/login", {
        email,
        password,
        device_label: navigator.platform ?? "",
      });
      // Set the CSRF token directly rather than relying solely on
      // AuthContext's `useEffect(() => setCsrfToken(data?.csrf_token), [data])`
      // to pick it up from the query cache - see the setQueryData ordering
      // note just below for why that hand-off is race-prone. Setting it here
      // is synchronous and race-free.
      setCsrfToken(me.csrf_token);
      // Seed "me" BEFORE touching anything else, and never tear it down:
      // queryClient.clear()/removeQueries(everything) destroys the "me"
      // query's own internal state while AuthProvider's useQuery still has
      // an active, mounted observer on it - that observer transiently sees
      // stale-then-correct data across two renders. A component that reacts
      // to `me` by navigating (App.tsx's IndexRoute) can act on the stale
      // first render and redirect the vendor to the wrong app before the
      // correct render ever happens, and nothing then navigates it back
      // (confirmed: logging out of a both-apps company and into a
      // RepairFlow-only one intermittently got stuck on the app chooser).
      // Setting "me" first, and only ever removing every *other* query,
      // closes that window entirely.
      queryClient.setQueryData(queryKeys.me, me);
      // Logging in over an already-authenticated session (no explicit
      // logout first - e.g. switching companies mid-manual-test) must not
      // leave the previous company's cached data (dashboard, customers,
      // orders, ...) visible: none of those query keys are company-scoped
      // (lib/queryKeys.ts), so without a clear they'd keep showing stale
      // cross-company data until each query's own staleTime expires.
      // logout() already clears the cache for this reason - login must too.
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      // The remembered "last used app" (shell/lastApp.ts) is the same kind
      // of cross-company leak risk if left in place - a RepairFlow+
      // PropertyFlow company's stale choice must never decide where a
      // different, just-logged-in company lands.
      clearLastApp();
      // See lib/queryNotify.ts: without this, RequireAuth (App.tsx) can
      // evaluate the "/" route against the *previous* `me` (often none)
      // and bounce back to /login right after a successful login -
      // confirmed via a regression test that logs out of a both-apps
      // company and into a different one.
      await waitForQueryNotifications();
      const requestedNext = new URLSearchParams(location.search).get("next") ?? "/";
      const next = isSafeNext(requestedNext, me.active_modules) ? requestedNext : "/";
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
