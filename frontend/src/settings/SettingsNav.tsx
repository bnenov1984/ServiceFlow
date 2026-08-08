/** Settings sub-nav: both settings screens are Owner-only, single-purpose
 * pages reached via the same "Настройки" shell nav entry - this is the
 * minimal wayfinding between them, not a full settings shell/tab system. */

import { NavLink } from "react-router-dom";
import { t } from "../i18n/bg";

function linkClass({ isActive }: { isActive: boolean }): string {
  return `rounded-lg px-3 py-1.5 text-sm font-medium ${
    isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50"
  }`;
}

export function SettingsNav() {
  return (
    <nav className="mb-4 flex gap-2">
      <NavLink to="/settings/employees" className={linkClass}>
        {t("settings.nav_employees")}
      </NavLink>
      <NavLink to="/settings/company" className={linkClass}>
        {t("settings.nav_company")}
      </NavLink>
    </nav>
  );
}
