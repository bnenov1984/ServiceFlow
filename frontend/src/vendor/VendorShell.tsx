/** Vendor Console layout — minimal top bar + outlet. No sidebar: two screens
 * (companies list/detail) don't need one. Never linked from the tenant
 * `AppShell` (ADR-BOS-009) — this is its own, separate route tree. */

import { Outlet, useNavigate } from "react-router-dom";
import { t } from "../i18n/bg";
import { useVendorAuth } from "./VendorAuthContext";

export function VendorShell() {
  const { me, logout } = useVendorAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/vendor/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <span className="text-lg font-semibold text-slate-900">{t("vendor.title")}</span>
        <div className="flex items-center gap-4">
          {me && <span className="text-sm text-slate-600">{me.name}</span>}
          <button
            type="button"
            onClick={() => void onLogout()}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 min-h-touch"
          >
            {t("vendor.logout")}
          </button>
        </div>
      </header>
      <main className="flex-1 px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
