/** MoneyCard (docs/15 §6.5): parts+labor computed total; „Фактура" disabled
 * per the approved grayed-nav treatment (Etap 4). */

import { t } from "../i18n/bg";

export function MoneyCard({ estimatedTotal }: { estimatedTotal: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.money")}
      </h3>
      <p className="text-2xl font-bold tabular-nums text-slate-900">
        {estimatedTotal.toFixed(2)} €
      </p>
      <p className="mb-3 text-xs text-slate-400">{t("order.money_hint")}</p>
      <button
        type="button"
        disabled
        title={t("nav.coming_soon")}
        className="cursor-not-allowed rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-300 min-h-touch"
      >
        {t("order.invoice_button")}
      </button>
    </div>
  );
}
