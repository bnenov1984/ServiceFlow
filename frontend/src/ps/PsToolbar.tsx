/** PropertyFlow's own workspace toolbar — rendered inside PsPage's content
 * area, not the global Business OS header (AppShell owns brand/app-switcher/
 * account only; see shell/AppShell.tsx's GlobalHeader doc comment). Календар
 * has no view behind it yet, so it's greyed the same way the sidebar treats
 * Фактури/Настройки (AppShell's GrayedNavItem) rather than invented here. */

import { t } from "../i18n/bg";

function FunnelIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
         strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden>
      <path d="M4 5h16l-6 7v6l-4 2v-8z" />
    </svg>
  );
}

export function PsToolbar({
  activeOnly,
  onToggleActiveOnly,
  onNewAssignment,
}: {
  activeOnly: boolean;
  onToggleActiveOnly: () => void;
  onNewAssignment: () => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t("ps.dashboard_title")}</h1>
        <p className="text-sm text-slate-500">{t("ps.dashboard_subtitle")}</p>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onNewAssignment}
          className="whitespace-nowrap rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 min-h-touch"
        >
          {t("ps.new_assignment")}
        </button>
        <span
          title={t("nav.coming_soon")}
          aria-disabled
          className="cursor-not-allowed whitespace-nowrap rounded-lg border border-slate-200 px-4 py-2 font-medium text-slate-300 min-h-touch"
        >
          {t("ps.calendar")}
        </span>
        <button
          type="button"
          aria-pressed={activeOnly}
          title={t("ps.filter_toggle_title")}
          onClick={onToggleActiveOnly}
          className={`rounded-lg border p-2 min-h-touch min-w-touch ${
            activeOnly ? "border-blue-400 bg-blue-50 text-blue-700" : "border-slate-300 text-slate-500 hover:bg-slate-50"
          }`}
        >
          <FunnelIcon />
        </button>
      </div>
    </div>
  );
}
