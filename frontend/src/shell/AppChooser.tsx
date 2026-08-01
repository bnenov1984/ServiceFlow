/** Standalone screens for the two routing edge cases IndexRoute (App.tsx)
 * hands off to - deliberately rendered outside AppShell (no per-app nav/
 * toolbar makes sense when there's no "current app" yet, or none at all),
 * mirroring LoginPage.tsx's own standalone <main> treatment. */

import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { t } from "../i18n/bg";
import { setLastApp } from "./lastApp";

function StandaloneCard({ children }: { children: ReactNode }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center">
        {children}
        <button
          type="button"
          onClick={() => void logout().catch(() => {}).finally(() => navigate("/login"))}
          className="mt-6 text-sm text-slate-500 hover:underline"
        >
          {t("shell.logout")}
        </button>
      </div>
    </main>
  );
}

/** Both RepairFlow and PropertyFlow active, no remembered preference yet
 * (lastApp.ts) - the vendor's own choice, not RepairFlow-by-default. */
export function AppChooserPage() {
  const navigate = useNavigate();

  const choose = (appId: string, path: string) => {
    setLastApp(appId);
    navigate(path, { replace: true });
  };

  return (
    <StandaloneCard>
      <h1 className="mb-2 text-xl font-semibold text-slate-900">{t("shell.chooser_title")}</h1>
      <p className="mb-6 text-sm text-slate-500">{t("shell.chooser_hint")}</p>
      <div className="flex flex-col gap-3">
        <button
          type="button"
          onClick={() => choose("repairflow", "/")}
          className="rounded-lg border border-slate-300 px-4 py-3 font-semibold text-slate-800 hover:bg-slate-50 min-h-touch"
        >
          {t("app.repairflow")}
        </button>
        <button
          type="button"
          onClick={() => choose("propertyflow", "/ps")}
          className="rounded-lg border border-slate-300 px-4 py-3 font-semibold text-slate-800 hover:bg-slate-50 min-h-touch"
        >
          {t("app.propertyflow")}
        </button>
      </div>
    </StandaloneCard>
  );
}

/** Neither RepairFlow nor PropertyFlow active - a real, reachable state
 * since the 01.08.2026 PO decision that no application is active by
 * default. Never renders RepairFlow (or any app's) chrome. */
export function NoActiveAppsPage() {
  return (
    <StandaloneCard>
      <h1 className="mb-2 text-xl font-semibold text-slate-900">{t("shell.no_active_apps_title")}</h1>
      <p className="text-sm text-slate-500">{t("shell.no_active_apps_hint")}</p>
    </StandaloneCard>
  );
}
